"""Local web dashboard for the active Pi station; no extra camera or UART owner."""

from collections import Counter, deque
import csv
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import queue
import re
import secrets
import ssl
import threading
import time
import unicodedata
from urllib.parse import urlsplit


HERE = Path(__file__).resolve().parent
STATE = re.compile(r'^STATE (\d+) ([A-Z_]+) ([01]) ([01]) ([01]) ([01]) ([01]) (\d+) (\d+) ([01])(?: (\d+) (\d+)(?: (\d+) (\d+) (\d+) (\d+) ([01]))?)?$')
ACK = re.compile(r'^OPACK (\d+) (\d+) (OK|DENY)$')
IMAGE = re.compile(r'^/api/image/([0-9_]+)/([0-9_]+_result\.jpg)$')
RUN = re.compile(r'^/api/run/([a-z0-9][a-z0-9_-]{0,63})(?:\.(csv|json))?$')
CAPTURE_FILE = re.compile(r'^(\d+)_(\d+)\.json$')
RUN_ID = re.compile(r'^[a-z0-9][a-z0-9_-]{0,63}$')
COMMANDS = {'STOP', 'START', 'DRY', 'SORT', 'SPEED', 'LIGHT',
            'SERVO_ANGLE', 'SERVO_SPEED', 'SERVO_HOLD'}
SERVO_RANGES = {'SERVO_ANGLE': (1, 90), 'SERVO_SPEED': (30, 240),
                'SERVO_HOLD': (150, 1500)}
CAMERA_FIELDS = {
    'brightness': 'Độ sáng', 'contrast': 'Tương phản', 'gain': 'Gain',
    'exposure_time_absolute': 'Phơi sáng', 'white_balance_temperature': 'Cân bằng trắng',
    'gamma': 'Gamma', 'saturation': 'Độ bão hòa', 'sharpness': 'Độ nét',
}


def parse_device_line(line):
    match = STATE.fullmatch(line)
    if match:
        (session, state, motor, sorting, ready, camera, gate, count, box_id, fault,
         speed, light, servo_angle, servo_speed, servo_hold, servo_effective,
         servo_moving) = match.groups()
        if (speed is None) != (light is None) or (speed is not None and
                (not 0 <= int(speed) <= 255 or not 0 <= int(light) <= 255)):
            return None
        if servo_angle is not None and not (1 <= int(servo_angle) <= 90 and
                30 <= int(servo_speed) <= 240 and 150 <= int(servo_hold) <= 1500 and
                int(servo_effective) >= int(servo_hold)):
            return None
        return ('state', {
            'session': int(session), 'state': state, 'motor': motor == '1',
            'sorting': sorting == '1', 'ready': ready == '1',
            'camera': camera == '1', 'gate': gate == '1',
            'queue': int(count), 'box_id': int(box_id), 'fault': fault == '1',
            'motor_speed': int(speed) if speed is not None else None,
            'light_level': int(light) if light is not None else None,
            'servo_angle': int(servo_angle) if servo_angle is not None else None,
            'servo_speed': int(servo_speed) if servo_speed is not None else None,
            'servo_hold': int(servo_hold) if servo_hold is not None else None,
            'servo_effective': int(servo_effective) if servo_effective is not None else None,
            'servo_moving': servo_moving == '1' if servo_moving is not None else None,
        })
    match = ACK.fullmatch(line)
    if match:
        return ('ack', {'session': int(match[1]), 'sequence': int(match[2]),
                        'accepted': match[3] == 'OK'})
    return None


class Dashboard:
    def __init__(self, bind, port, token, captures, tls_cert=None, tls_key=None,
                 local_trust=False, camera=None, camera_controls=None, camera_profile=None):
        if len(token) < 24:
            raise ValueError('DATN_DASHBOARD_TOKEN must contain at least 24 characters')
        local = bind in ('127.0.0.1', 'localhost', '::1')
        if local_trust and not local:
            raise ValueError('Local trust requires a loopback bind')
        if not local and not (tls_cert and tls_key):
            raise ValueError('Network access requires a TLS certificate and key')
        self.bind, self.port, self.token = bind, port, token
        self.local_trust = local_trust
        self.camera = camera
        self.camera_controls = camera_controls
        self.camera_profile = Path(camera_profile) if camera_profile else None
        self.settings_busy = False
        self.captures = Path(captures).resolve()
        self.lock = threading.Lock()
        self.archive_lock = threading.Lock()
        self.runs_lock = threading.RLock()
        self.run_index_path = self.captures/'dashboard_runs.json'
        self.named_runs = self._load_named_runs()
        self.archive_cache_key = None
        self.archive_cache = {}
        self.preview_condition = threading.Condition(self.lock)
        self.commands = queue.Queue(maxsize=8)
        self.device = None
        self.device_at = 0.0
        self.station = {'ready': False, 'camera': False, 'fault': None,
                        'busy': False, 'pending': False, 'queue': 0}
        self.counts = Counter()
        self.recent = deque(maxlen=20)
        self._restore_active_run()
        self.operations = {}
        self.closed = False
        self.preview_requested = 0.0
        self.preview_at = 0.0
        self.preview_jpeg = None
        self.preview_sequence = 0
        self.preview_times = deque(maxlen=60)
        # Keep the operator view smooth while the station is idle. Encoding is
        # suspended as soon as capture/inference becomes active, so NCNN keeps
        # priority over the dashboard.
        self.preview_period = 1.0 / 30.0
        self.preview_encoded_at = 0.0
        self.preview_stop = threading.Event()
        handler = self._handler()
        self.server = ThreadingHTTPServer((bind, port), handler)
        self.server.daemon_threads = True
        if tls_cert or tls_key:
            if not (tls_cert and tls_key):
                raise ValueError('Both TLS certificate and key are required')
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.load_cert_chain(tls_cert, tls_key)
            self.server.socket = context.wrap_socket(self.server.socket, server_side=True)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.preview_thread = None
        if camera is not None:
            self.preview_thread = threading.Thread(target=self._encode_preview, daemon=True)
            self.preview_thread.start()

    def _encode_preview(self):
        import cv2
        while not self.preview_stop.wait(.001):
            with self.lock:
                requested = self.preview_requested
            inspection_active = bool(self.station.get('busy') or
                                     self.station.get('pending') or
                                     self.station.get('queue'))
            if time.monotonic() - requested > 3:
                continue
            if inspection_active:
                continue
            if time.monotonic() - self.preview_encoded_at < self.preview_period:
                continue
            frame, stamp = self.camera.read()
            if frame is None or time.monotonic() - stamp > .75:
                continue
            with self.lock:
                if stamp <= self.preview_at:
                    continue
            try:
                height, width = frame.shape[:2]
                if width > 480:
                    frame = cv2.resize(frame, (480, round(height * 480 / width)))
                success, encoded = cv2.imencode('.jpg', frame,
                                                [cv2.IMWRITE_JPEG_QUALITY, 55])
                if success:
                    with self.preview_condition:
                        self.preview_jpeg = encoded.tobytes()
                        self.preview_at = stamp
                        self.preview_encoded_at = time.monotonic()
                        self.preview_sequence += 1
                        self.preview_times.append(time.monotonic())
                        self.preview_condition.notify_all()
            except (cv2.error, ValueError):
                continue

    def live_snapshot(self, previous=0):
        deadline = time.monotonic() + 1.25
        with self.preview_condition:
            self.preview_requested = time.monotonic()
            while not self.closed:
                if (self.preview_jpeg is not None and self.preview_sequence > previous
                        and time.monotonic() - self.preview_at <= 1):
                    return self.preview_jpeg, self.preview_sequence
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self.preview_condition.wait(remaining)
            return None

    def update_station(self, **fields):
        with self.lock:
            self.station.update(fields)

    def inspection(self, packet, image_folder):
        key = packet.get('key')
        if not isinstance(key, (list, tuple)) or len(key) != 2:
            return
        stem = '%s_%s' % tuple(key)
        row = {'id': stem, 'result': packet.get('result'),
               'delivered': bool(packet.get('delivered')),
               'reason': packet.get('reason'), 'total_ms': packet.get('request_to_result_ms'),
               'image': f'/api/image/{image_folder}/{stem}_result.jpg',
               'at': time.time()}
        with self.lock:
            if packet.get('delivered'):
                self.counts[packet.get('result')] += 1
            self.recent.appendleft(row)

    def _load_named_runs(self):
        if not self.run_index_path.is_file():
            return []
        try:
            payload = json.loads(self.run_index_path.read_text(encoding='utf-8'))
        except (OSError, ValueError, TypeError):
            return []
        records = payload.get('runs') if isinstance(payload, dict) else None
        if not isinstance(records, list):
            return []
        valid = []
        active_seen = False
        for record in reversed(records):
            if not isinstance(record, dict):
                continue
            run_id, name = record.get('id'), record.get('name')
            started_at, ended_at = record.get('started_at'), record.get('ended_at')
            if (not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id)
                    or not isinstance(name, str) or not name.strip()
                    or not isinstance(started_at, (int, float))
                    or (ended_at is not None and not isinstance(ended_at, (int, float)))):
                continue
            # Only the most recent unfinished record may remain active after a restart.
            if ended_at is None:
                if active_seen:
                    ended_at = started_at
                active_seen = True
            valid.append({'id': run_id, 'name': name.strip()[:80],
                          'started_at': float(started_at),
                          'ended_at': float(ended_at) if ended_at is not None else None})
        valid.reverse()
        return valid

    def _save_named_runs(self):
        self.captures.mkdir(parents=True, exist_ok=True)
        payload = {'version': 1, 'runs': self.named_runs}
        temporary = self.run_index_path.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(self.run_index_path)

    @staticmethod
    def _validate_run_name(value):
        if not isinstance(value, str):
            return None
        name = ' '.join(value.split())
        if not 1 <= len(name) <= 80 or any(ord(character) < 32 for character in name):
            return None
        return name

    def active_run(self):
        with self.runs_lock:
            record = next((item for item in reversed(self.named_runs)
                           if item['ended_at'] is None), None)
            return dict(record) if record else None

    def _restore_active_run(self):
        record = self.active_run()
        if record is None:
            return
        detail = self._named_run_detail(record)
        for row in detail['results'][:20]:
            self.recent.append(row)
        for row in detail['results']:
            if row.get('delivered'):
                self.counts[row.get('result')] += 1

    def create_run(self, name):
        name = self._validate_run_name(name)
        if name is None:
            return None, 'Tên phiên phải có từ 1 đến 80 ký tự.'
        with self.lock:
            device = self._fresh_device()
            if not self._stopped_clear(device):
                return None, 'Dừng băng tải, lấy hết hộp và chờ trạm rảnh trước khi tạo phiên mới.'
        now = time.time()
        with self.runs_lock:
            for record in self.named_runs:
                if record['ended_at'] is None:
                    record['ended_at'] = now
            run_id = time.strftime('r_%Y%m%d_%H%M%S', time.localtime(now))
            run_id += '_' + secrets.token_hex(2)
            record = {'id': run_id, 'name': name, 'started_at': now, 'ended_at': None}
            self.named_runs.append(record)
            self._save_named_runs()
        with self.lock:
            self.counts.clear()
            self.recent.clear()
        return self._named_run_detail(record), None

    @staticmethod
    def _filename_slug(value):
        normalized = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode()
        slug = re.sub(r'[^a-zA-Z0-9_-]+', '_', normalized).strip('_')
        return slug[:40] or 'phien'

    def _capture_cache_key(self):
        folders = []
        if self.captures.is_dir():
            for folder in self.captures.iterdir():
                if folder.is_dir() and folder.name != 'exports' and re.fullmatch(r'[0-9_]+', folder.name):
                    try:
                        folders.append((folder.name, folder.stat().st_mtime_ns))
                    except OSError:
                        continue
        return tuple(sorted(folders))

    def _read_archived_runs(self):
        """Read audit JSON only on explicit run-history requests, never in the AI path."""
        with self.archive_lock:
            cache_key = self._capture_cache_key()
            if cache_key == self.archive_cache_key:
                return self.archive_cache
            runs = {}
            for folder_name, _ in cache_key:
                folder = self.captures/folder_name
                for record_path in folder.glob('*.json'):
                    match = CAPTURE_FILE.fullmatch(record_path.name)
                    if not match:
                        continue
                    session, box_id = int(match[1]), int(match[2])
                    try:
                        data = json.loads(record_path.read_text(encoding='utf-8'))
                        modified = record_path.stat().st_mtime
                    except (OSError, ValueError, TypeError):
                        continue
                    result = data.get('result')
                    delivered = bool(data.get('delivered'))
                    row = {
                        'id': f'{session}_{box_id}', 'session': session, 'box_id': box_id,
                        'result': result, 'delivered': delivered,
                        'reason': data.get('reason'),
                        'capture_ms': data.get('capture_ms'),
                        'inference_ms': data.get('inference_ms'),
                        'total_ms': data.get('request_to_result_ms'),
                        'image': f'/api/image/{folder_name}/{session}_{box_id}_result.jpg',
                        'at': modified,
                    }
                    runs.setdefault(session, []).append(row)
            for rows in runs.values():
                rows.sort(key=lambda item: (item['at'], item['box_id']))
            self.archive_cache_key, self.archive_cache = cache_key, runs
            return runs

    @staticmethod
    def _summary(run_id, name, rows, started_at=None, ended_at=None, active=False,
                 legacy_session=None):
        counts = Counter(row.get('result') for row in rows if row.get('delivered'))
        times = [row['at'] for row in rows]
        return {
            'id': run_id, 'name': name, 'session': legacy_session, 'active': active,
            'count': len(rows),
            'counts': {name: counts[name] for name in ('PASS', 'DEFECT', 'ERROR')},
            'started_at': started_at if started_at is not None else (min(times) if times else None),
            'ended_at': ended_at if ended_at is not None else (max(times) if times else None),
        }

    @staticmethod
    def _rows_in_interval(archives, started_at, ended_at):
        rows = [row for group in archives.values() for row in group
                if row['at'] >= started_at and (ended_at is None or row['at'] < ended_at)]
        rows.sort(key=lambda item: (item['at'], item['session'], item['box_id']))
        return rows

    def _named_run_detail(self, record, archives=None):
        archives = self._read_archived_runs() if archives is None else archives
        rows = self._rows_in_interval(archives, record['started_at'], record['ended_at'])
        summary = self._summary(record['id'], record['name'], rows,
                                record['started_at'], record['ended_at'],
                                record['ended_at'] is None)
        return {**summary, 'results': list(reversed(rows))}

    def list_runs(self):
        archives = self._read_archived_runs()
        with self.runs_lock:
            named = [dict(record) for record in self.named_runs]
        summaries = []
        for record in named:
            detail = self._named_run_detail(record, archives)
            detail.pop('results', None)
            summaries.append(detail)
        # Keep audit records from before named runs were introduced accessible as legacy runs.
        claimed = [(record['started_at'], record['ended_at']) for record in named]
        for session, rows in archives.items():
            unclaimed = [row for row in rows if not any(
                row['at'] >= start and (end is None or row['at'] < end)
                for start, end in claimed)]
            if unclaimed:
                summaries.append(self._summary(str(session), f'Phiên cũ {session}', unclaimed,
                                               legacy_session=session))
        summaries.sort(key=lambda item: (bool(item.get('active')),
                                         item['ended_at'] or item['started_at'] or 0),
                       reverse=True)
        active = next((item for item in summaries if item.get('active')), None)
        return {'runs': summaries, 'active_id': active['id'] if active else None}

    def run_detail(self, run_id):
        archives = self._read_archived_runs()
        with self.runs_lock:
            record = next((dict(item) for item in self.named_runs if item['id'] == run_id), None)
            intervals = [(item['started_at'], item['ended_at']) for item in self.named_runs]
        if record is not None:
            return self._named_run_detail(record, archives)
        if not run_id.isdigit():
            return None
        session = int(run_id)
        rows = archives.get(session)
        if rows is None:
            return None
        rows = [row for row in rows if not any(
            row['at'] >= start and (end is None or row['at'] < end)
            for start, end in intervals)]
        if not rows:
            return None
        return {**self._summary(run_id, f'Phiên cũ {session}', rows,
                                legacy_session=session), 'results': list(reversed(rows))}

    def run_export(self, run_id, kind):
        detail = self.run_detail(run_id)
        if detail is None:
            return None
        exports = self.captures/'exports'
        exports.mkdir(parents=True, exist_ok=True)
        if kind == 'json':
            data = json.dumps(detail, ensure_ascii=False, indent=2).encode('utf-8')
            content_type = 'application/json; charset=utf-8'
        else:
            output = io.StringIO(newline='')
            fields = ['ten_phien', 'ma_phien', 'id_hop', 'session_esp32', 'box_id',
                      'ket_qua', 'da_gui_esp', 'ly_do',
                      'capture_ms', 'ai_ms', 'capture_to_result_ms', 'thoi_gian', 'anh']
            writer = csv.DictWriter(output, fieldnames=fields)
            writer.writeheader()
            for row in reversed(detail['results']):
                writer.writerow({
                    'ten_phien': detail['name'], 'ma_phien': detail['id'],
                    'id_hop': row['id'], 'session_esp32': row['session'],
                    'box_id': row['box_id'],
                    'ket_qua': row.get('result') or '', 'da_gui_esp': row['delivered'],
                    'ly_do': row.get('reason') or '', 'capture_ms': row.get('capture_ms'),
                    'ai_ms': row.get('inference_ms'),
                    'capture_to_result_ms': row.get('total_ms'),
                    'thoi_gian': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(row['at'])),
                    'anh': row.get('image') or '',
                })
            data = ('\ufeff' + output.getvalue()).encode('utf-8')
            content_type = 'text/csv; charset=utf-8'
        filename = f"run_{run_id}_{self._filename_slug(detail['name'])}.{kind}"
        target = exports/filename
        temporary = exports/(filename+'.tmp')
        temporary.write_bytes(data)
        temporary.replace(target)
        return data, content_type, filename

    def device_line(self, line):
        parsed = parse_device_line(line)
        if not parsed:
            return False
        kind, data = parsed
        with self.lock:
            if kind == 'state':
                self.device, self.device_at = data, time.monotonic()
            else:
                item = self.operations.get(data['sequence'])
                if item and item['session'] == data['session'] and item['state'] == 'sent':
                    item['state'] = 'accepted' if data['accepted'] else 'denied'
                    item['updated'] = time.time()
        return True

    def _fresh_device(self):
        return self.device if self.device and time.monotonic() - self.device_at < 2 else None

    def snapshot(self):
        active_run = self.active_run()
        with self.lock:
            device = self._fresh_device()
            for item in self.operations.values():
                if item['state'] == 'sent' and time.time() - item['updated'] > 2:
                    item['state'], item['updated'] = 'timeout', time.time()
            return {'station': dict(self.station), 'device': dict(device) if device else None,
                    'local_trust': self.local_trust,
                    'active_run': active_run,
                    'counts': {x: self.counts[x] for x in ('PASS', 'DEFECT', 'ERROR')},
                    'recent': list(self.recent),
                    'operations': list(self.operations.values())[-12:],
                    'preview_fps': ((len(self.preview_times)-1) /
                                    (self.preview_times[-1]-self.preview_times[0])
                                    if len(self.preview_times) > 1 else 0),
                    'time': time.time()}

    def _stopped_clear(self, device):
        return bool(device and device['state'] == 'STOPPED' and not device['motor']
                    and not device['queue'] and not device['camera'] and not device['gate']
                    and not device['fault'] and not self.station['busy']
                    and not self.station['pending'] and self.station['queue'] == 0
                    and not self.settings_busy and not any(
                        item['verb'] == 'START' and item['state'] in ('queued', 'sent')
                        for item in self.operations.values()))

    def settings(self):
        with self.lock:
            device = self._fresh_device()
            editable = self._stopped_clear(device)
        values = []
        error = None
        if self.camera_controls is not None:
            try:
                for name, control in self.camera_controls.controls().items():
                    if name in CAMERA_FIELDS and control.active:
                        values.append({'name': name, 'label': CAMERA_FIELDS[name],
                                       'value': control.value, 'min': control.minimum,
                                       'max': control.maximum, 'step': control.step})
            except Exception as exc:
                error = str(exc)
        saved = {}
        saved_at = None
        if self.camera_profile and self.camera_profile.is_file():
            try:
                profile = json.loads(self.camera_profile.read_text(encoding='utf-8'))
                saved = profile.get('values', profile)
                saved_at = profile.get('saved_at')
            except (OSError, ValueError, TypeError):
                error = 'Không đọc được cấu hình camera đã lưu'
        for control in values:
            control['saved'] = saved.get(control['name'])
        return {'editable': editable, 'camera': values, 'camera_error': error,
                'camera_saved': bool(saved), 'camera_saved_at': saved_at}

    def camera_action(self, action, name=None, value=None):
        if self.camera_controls is None or self.camera_profile is None:
            return None, 'Camera controls unavailable'
        if action == 'CAMERA_APPLY':
            if name not in CAMERA_FIELDS or type(value) is not int:
                return None, 'Invalid camera control'
        elif action not in ('CAMERA_SAVE', 'CAMERA_RESTORE'):
            return None, 'Invalid camera action'
        with self.lock:
            if not self._stopped_clear(self._fresh_device()):
                return None, 'Stop and clear the conveyor and sensors first'
            self.settings_busy = True
        try:
            if action == 'CAMERA_APPLY':
                control = self.camera_controls.controls().get(name)
                if control is None or not control.active:
                    return None, 'Camera control unavailable'
                control.validate(value)
                self.camera_controls.apply({name: value})
            elif action == 'CAMERA_SAVE':
                backup = self.camera_profile.with_name('camera_profile.before_dashboard_20261026.json')
                if self.camera_profile.is_file() and not backup.exists():
                    import shutil
                    shutil.copy2(self.camera_profile, backup)
                self.camera_controls.save_profile(self.camera_profile)
            else:
                backup = self.camera_profile.with_name('camera_profile.before_dashboard_20261026.json')
                if not backup.is_file():
                    return None, 'No original camera profile backup'
                self.camera_controls.load_profile(backup)
                self.camera_controls.save_profile(self.camera_profile)
            return self.settings(), None
        except Exception as exc:
            return None, str(exc)
        finally:
            with self.lock:
                self.settings_busy = False

    def submit(self, verb, value=None):
        if verb not in COMMANDS:
            return None, 'Unsupported command'
        if verb in {'SPEED', 'LIGHT', *SERVO_RANGES}:
            minimum, maximum = SERVO_RANGES.get(verb, (1, 255) if verb == 'SPEED' else (0, 255))
            if type(value) is not int or not minimum <= value <= maximum:
                return None, 'Setting must be an integer within device range'
        elif value is not None:
            return None, 'Unexpected setting value'
        with self.lock:
            device = self._fresh_device()
            if not device:
                return None, 'No recent ESP32 state'
            if verb == 'START':
                if self.active_run() is None:
                    return None, 'Create a named run before START'
                if not (self.station['ready'] and self.station['camera']
                        and not self.station['fault'] and not self.station['busy']
                        and not self.station['pending'] and self.station['queue'] == 0
                        and not self.settings_busy):
                    return None, 'Pi station is not ready or has pending work'
            if verb != 'STOP':
                if not (device['state'] == 'STOPPED' and not device['motor']
                        and device['queue'] == 0 and not device['camera']
                        and not device['gate'] and not device['fault']
                        and not self.settings_busy):
                    return None, 'Stop and clear the conveyor and sensors first'
            if verb in ('SPEED', 'LIGHT') and device.get('motor_speed') is None:
                return None, 'ESP32 firmware does not report adjustable settings'
            if verb in ('SPEED', 'LIGHT') and not self._stopped_clear(device):
                return None, 'Pi inspection is still active'
            if verb in SERVO_RANGES:
                if device.get('servo_angle') is None:
                    return None, 'ESP32 firmware does not report servo settings'
                if not self._stopped_clear(device) or device.get('servo_moving'):
                    return None, 'Stop and clear the conveyor; wait for servo to park'
            if verb == 'START' and not device['ready']:
                return None, 'ESP32 has not received Pi READY'
            if verb == 'START' and device.get('motor_speed') is not None and (
                    device['motor_speed'] == 0 or device['light_level'] == 0):
                return None, 'Set nonzero motor speed and light before START'
            sequence = secrets.randbelow(0xffffffff - 1) + 1
            while sequence in self.operations:
                sequence = secrets.randbelow(0xffffffff - 1) + 1
            item = {'sequence': sequence, 'session': device['session'], 'verb': verb, 'value': value,
                    'state': 'queued', 'updated': time.time()}
            try:
                self.commands.put_nowait(item)
            except queue.Full:
                return None, 'Command queue is full'
            self.operations[sequence] = item
            if len(self.operations) > 64:
                oldest = next(iter(self.operations))
                self.operations.pop(oldest)
            return sequence, None

    def drain(self, send, session, event):
        for _ in range(8):
            try:
                item = self.commands.get_nowait()
            except queue.Empty:
                break
            with self.lock:
                current = self._fresh_device()
                valid = current and current['session'] == session == item['session']
                if valid and item['verb'] != 'STOP':
                    valid = (current['state'] == 'STOPPED' and not current['motor']
                             and not current['queue'] and not current['camera']
                             and not current['gate'] and not current['fault'])
                if valid and item['verb'] == 'START':
                    valid = (self.active_run() is not None and current['ready'] and self.station['ready']
                             and self.station['camera'] and not self.station['fault']
                             and not self.station['busy'] and not self.station['pending']
                             and self.station['queue'] == 0 and not self.settings_busy)
                    if valid and current.get('motor_speed') is not None:
                        valid = current['motor_speed'] > 0 and current['light_level'] > 0
                if valid and item['verb'] in ('SPEED', 'LIGHT'):
                    valid = self._stopped_clear(current) and current.get('motor_speed') is not None
                if valid and item['verb'] in SERVO_RANGES:
                    valid = (self._stopped_clear(current) and
                             current.get('servo_angle') is not None and not current.get('servo_moving'))
                if not valid:
                    item['state'], item['updated'] = 'cancelled', time.time()
                    event('operator_command', verb=item['verb'], state='cancelled')
                    continue
                item['state'], item['updated'] = 'sent', time.time()
            suffix = f" {item['value']}" if item['value'] is not None else ''
            send(f"OP {item['session']} {item['sequence']} {item['verb']}{suffix}")
            event('operator_command', verb=item['verb'], sequence=item['sequence'], state='sent')

    def _handler(self):
        dashboard = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'

            def authorized(self):
                if dashboard.local_trust and self.client_address[0] in ('127.0.0.1', '::1'):
                    host = self.headers.get('Host', '')
                    allowed = (f'127.0.0.1:{dashboard.server.server_port}',
                               f'localhost:{dashboard.server.server_port}')
                    origin = self.headers.get('Origin')
                    if host in allowed and (not origin or origin == 'http://' + host):
                        return True
                return secrets.compare_digest(self.headers.get('Authorization', ''),
                                              'Bearer ' + dashboard.token)

            def respond(self, status, data, content_type, extra_headers=None):
                self.send_response(status)
                self.send_header('Content-Type', content_type)
                self.send_header('Cache-Control', 'no-store')
                self.send_header('X-Content-Type-Options', 'nosniff')
                for name, value in (extra_headers or {}).items():
                    self.send_header(name, value)
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def json(self, status, value):
                self.respond(status, json.dumps(value, ensure_ascii=False).encode(), 'application/json')

            def stream_preview(self):
                self.send_response(200)
                self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=datnframe')
                self.send_header('Cache-Control', 'no-store')
                self.send_header('X-Content-Type-Options', 'nosniff')
                self.send_header('Connection', 'close')
                self.end_headers()
                self.close_connection = True
                previous = 0
                while not dashboard.closed:
                    frame = dashboard.live_snapshot(previous)
                    if frame is None:
                        continue
                    jpeg, previous = frame
                    part = (b'--datnframe\r\nContent-Type: image/jpeg\r\nContent-Length: '
                            + str(len(jpeg)).encode() + b'\r\n\r\n' + jpeg + b'\r\n')
                    try:
                        self.wfile.write(part)
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError, OSError):
                        break

            def do_GET(self):
                path = urlsplit(self.path).path
                if path == '/':
                    self.respond(200, (HERE/'dashboard.html').read_bytes(), 'text/html; charset=utf-8')
                elif path in ('/dashboard.css', '/dashboard.js'):
                    kind = 'text/css' if path.endswith('.css') else 'text/javascript'
                    self.respond(200, (HERE/path[1:]).read_bytes(), kind+'; charset=utf-8')
                elif not self.authorized():
                    self.json(401, {'error': 'Unauthorized'})
                elif path == '/api/state':
                    self.json(200, dashboard.snapshot())
                elif path == '/api/settings':
                    self.json(200, dashboard.settings())
                elif path == '/api/runs':
                    self.json(200, dashboard.list_runs())
                elif path == '/api/live.jpg':
                    try:
                        previous = max(0, int(self.headers.get('X-Last-Frame', '0')))
                    except ValueError:
                        self.json(400, {'error': 'Invalid frame sequence'})
                        return
                    frame = dashboard.live_snapshot(previous)
                    if frame is None:
                        self.json(503, {'error': 'Camera preview is starting or unavailable'})
                    else:
                        jpeg, sequence = frame
                        self.respond(200, jpeg, 'image/jpeg',
                                     {'X-Frame-Sequence': str(sequence)})
                elif path == '/api/live.mjpg':
                    self.stream_preview()
                else:
                    run_match = RUN.fullmatch(path)
                    if run_match:
                        run_id, kind = run_match[1], run_match[2]
                        if kind:
                            exported = dashboard.run_export(run_id, kind)
                            if exported is None:
                                self.send_error(404)
                                return
                            data, content_type, filename = exported
                            self.respond(200, data, content_type,
                                         {'Content-Disposition': f'attachment; filename="{filename}"'})
                        else:
                            detail = dashboard.run_detail(run_id)
                            if detail is None:
                                self.send_error(404)
                            else:
                                self.json(200, detail)
                        return
                    match = IMAGE.fullmatch(path)
                    if not match:
                        self.send_error(404)
                        return
                    image = dashboard.captures/match[1]/match[2]
                    if not image.is_file():
                        self.send_error(404)
                        return
                    self.respond(200, image.read_bytes(), 'image/jpeg')

            def do_POST(self):
                path = urlsplit(self.path).path
                if path not in ('/api/command', '/api/settings', '/api/runs') or not self.authorized():
                    self.json(403, {'error': 'Forbidden'})
                    return
                if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                    self.json(415, {'error': 'JSON required'})
                    return
                try:
                    length = int(self.headers.get('Content-Length', '0'))
                    if length < 1 or length > 256:
                        raise ValueError('Invalid body size')
                    data = json.loads(self.rfile.read(length))
                except (ValueError, KeyError, TypeError):
                    self.json(400, {'error': 'Invalid command'})
                    return
                if path == '/api/runs':
                    result, error = dashboard.create_run(
                        data.get('name') if isinstance(data, dict) else None)
                    if error:
                        self.json(409, {'error': error})
                    else:
                        self.json(201, {'run': result})
                    return
                if path == '/api/settings':
                    target = data.get('target') if isinstance(data, dict) else None
                    if target in {'SPEED', 'LIGHT', *SERVO_RANGES}:
                        sequence, error = dashboard.submit(target, data.get('value'))
                    elif target in ('CAMERA_APPLY', 'CAMERA_SAVE', 'CAMERA_RESTORE'):
                        result, error = dashboard.camera_action(target, data.get('name'), data.get('value'))
                        if error:
                            self.json(409, {'error': error})
                        else:
                            self.json(200, result)
                        return
                    else:
                        self.json(400, {'error': 'Invalid setting'})
                        return
                else:
                    sequence, error = dashboard.submit(data.get('command') if isinstance(data, dict) else None)
                if error:
                    self.json(409, {'error': error})
                else:
                    self.json(202, {'sequence': sequence, 'state': 'queued'})

            def log_message(self, format, *args):
                pass

        return Handler

    def close(self):
        with self.preview_condition:
            self.closed = True
            self.preview_condition.notify_all()
        self.preview_stop.set()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        if self.preview_thread:
            self.preview_thread.join(timeout=2)
