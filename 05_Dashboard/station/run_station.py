"""Pi Stop&Go station with optional authenticated local operator dashboard."""
import argparse
from collections import deque
from datetime import datetime
import json
import multiprocessing as mp
import os
from pathlib import Path
import queue
import sys
import threading
import time

from startup_defaults import StartupDefaults
from station_protocol import Lines, Transactions
from dashboard import Dashboard, parse_device_line

DEFAULT_ROOT = Path('/home/cmh/Pi4_EdgeAI/runs/model_runtime_v4_20261029')


def environment(root):
    sys.path[:0] = [str(root/'src'), str(root)]
    os.environ['YOLO_CONFIG_DIR'] = str(root/'runs/yolo_config')
    os.environ['MPLCONFIGDIR'] = str(root/'runs/mplcache')
    os.environ['YOLO_AUTOINSTALL'] = 'false'
    os.environ['OMP_WAIT_POLICY'] = 'PASSIVE'


def ai_entry(root, pipe):
    """Run the frozen V4 pipeline; REVIEW is a protocol ERROR, never PASS."""
    try:
        environment(root)
        import cv2
        from current_pipeline import CurrentInspection
        config = json.loads((root/'config/app.json').read_text(encoding='utf-8'))
        pipeline = CurrentInspection(root, backend=config['whole_backend'],
                                     threads=config['torch_threads'])
        warmup = pipeline.warmup()
        pipe.send({'ready': True, 'warmup_ms': warmup, 'provenance': pipeline.provenance})
        while True:
            job = pipe.recv()
            if job is None:
                break
            key, frame = job
            start = time.monotonic()
            try:
                inspection = pipeline.inspect(frame)
                ai_decision = inspection['decision']
                protocol_result = (ai_decision if ai_decision in ('PASS', 'DEFECT')
                                   else config['review_protocol_result'])
                reason = inspection['reason']
                if ai_decision == 'REVIEW':
                    reason = 'REVIEW -> ERROR (fail-safe): ' + reason
                displayed = pipeline.annotate(frame, inspection)
                record = {
                    'release': config['release'],
                    'ai_decision': ai_decision,
                    'protocol_result': protocol_result,
                    'inspection': inspection,
                    'station_decision': protocol_result,
                    'station_decision_reason': reason,
                }
                pipe.send({'key': key, 'result': protocol_result, 'reason': reason,
                           'record': record, 'displayed': displayed,
                           'inference_ms': (time.monotonic()-start)*1000})
            except Exception as error:
                pipe.send({'key': key, 'result': 'ERROR', 'reason': repr(error), 'record': {}})
    except BaseException as error:
        try:
            pipe.send({'fatal': repr(error)})
        except (BrokenPipeError, EOFError, OSError):
            pass
    finally:
        pipe.close()


class Audit:
    def __init__(self, folder):
        self.folder = folder
        folder.mkdir(parents=True, exist_ok=False)
        self.error = None
        self.jobs = queue.Queue(maxsize=8)
        self.thread = threading.Thread(target=self.write, daemon=True)
        self.thread.start()

    def submit(self, item):
        try:
            self.jobs.put_nowait(item)
        except queue.Full:
            self.error = 'audit backlog full; restart station after checking disk'

    def write(self):
        import cv2
        while True:
            item = self.jobs.get()
            try:
                if item is None:
                    return
                key, frame, packet = item
                stem = self.folder/('%s_%s' % key)
                for suffix, image in (('_raw.jpg', frame), ('_result.jpg', packet.pop('displayed', frame))):
                    if not cv2.imwrite(str(stem)+suffix, image):
                        raise IOError('cannot save capture')
                Path(str(stem)+'.json').write_text(json.dumps(packet, indent=2), encoding='utf-8')
            except Exception as error:
                self.error = repr(error)
                print('AUDIT_ERROR', self.error, flush=True)
            finally:
                self.jobs.task_done()

    def close(self):
        self.jobs.put(None)
        self.thread.join(timeout=10)
        if self.thread.is_alive():
            print('AUDIT_ERROR pending disk writes; inspect session directory', flush=True)


def make_camera(index, profile):
    from pi_camera import PiCamera

    class CaptureCamera(PiCamera):
        def __init__(self):
            self.sequence = 0
            self.read_started = 0.
            super().__init__(index, width=640, height=480, profile_path=profile)

        def _read(self):
            try:
                while not self.stop.is_set():
                    if self.paused.is_set():
                        self.stop.wait(.01)
                        continue
                    with self.io_lock:
                        start = time.monotonic()
                        ok, frame = self.cap.read()
                    end = time.monotonic()
                    if ok:
                        with self.lock:
                            self.latest, self.stamp, self.read_started = frame, end, start
                            self.sequence += 1
                            self.frame_times.append(end)
                            self.read_times.append((end-start)*1000)
                    else:
                        self.stop.wait(.05)
                    self.stop.wait(.001)
            finally:
                self.cap.release()

        def healthy(self):
            with self.lock:
                return self.latest is not None and time.monotonic()-self.stamp < .5 and self.thread.is_alive()

        def token(self):
            with self.lock:
                return self.sequence

        def capture_after(self, requested, sequence):
            with self.lock:
                # Discard two completions to drain a read already in flight and
                # the one-buffer V4L2 backlog. No disk I/O or inference here.
                if (self.sequence < sequence+3 or self.read_started < requested
                        or time.monotonic()-self.stamp >= .25):
                    return None
                return self.latest.copy(), self.sequence, self.read_started, self.stamp

    return CaptureCamera()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=DEFAULT_ROOT)
    parser.add_argument('--port', default='/dev/serial0')
    parser.add_argument('--camera', type=int, default=0)
    parser.add_argument('--headless', action='store_true')
    parser.add_argument('--run-seconds', type=float, default=0)
    parser.add_argument('--dashboard', action='store_true', help='enable local operator web dashboard')
    parser.add_argument('--dashboard-bind', default='127.0.0.1')
    parser.add_argument('--dashboard-port', type=int, default=8768)
    parser.add_argument('--dashboard-local-trust', action='store_true',
                        help='trust loopback browser access through the Pi SSH tunnel')
    parser.add_argument('--dashboard-tls-cert', type=Path)
    parser.add_argument('--dashboard-tls-key', type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    environment(root)
    from integrity import verify
    verify(root)
    # Refuse accidental modification of station files after packaging.
    import hashlib
    addon = Path(__file__).resolve().parent
    manifest = json.loads((addon/'manifest.json').read_text())
    for name, expected in manifest['files_sha256'].items():
        if hashlib.sha256((addon/name).read_bytes()).hexdigest() != expected:
            raise RuntimeError('Station checksum mismatch: '+name)
    import cv2
    import serial
    import fcntl
    cv2.setNumThreads(1)
    profile = root.parent/'camera_profile.json'
    if not profile.is_file():
        raise FileNotFoundError('Expected current native camera profile: '+str(profile))
    # Prevent competing station instances before opening camera/UART.
    lock = (addon/'station.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    camera = uart = process = audit = dashboard = None
    try:
        camera = make_camera(args.camera, profile)
        uart = serial.Serial(args.port, 115200, timeout=.005, write_timeout=.2, exclusive=True)
        uart.reset_input_buffer()
        events = (addon/'events.jsonl').open('a', buffering=1)

        def event(name, **fields):
            row = {'event': name, 'monotonic': time.monotonic(), **fields}
            events.write(json.dumps(row)+'\n')
            print(json.dumps(row), flush=True)

        def send(line):
            data = (line+'\n').encode('ascii')
            if uart.write(data) != len(data):
                raise IOError('partial UART write')
            if not line.startswith('PING '):
                event('tx', line=line)

        ctx = mp.get_context('spawn')
        pipe, child = ctx.Pipe()
        process = ctx.Process(target=ai_entry, args=(root, child), daemon=True)
        process.start()
        child.close()
        audit = Audit(addon/'captures'/datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
        if args.dashboard:
            from camera_controls import V4L2Camera
            dashboard = Dashboard(args.dashboard_bind, args.dashboard_port,
                                  os.environ.get('DATN_DASHBOARD_TOKEN', ''),
                                  addon/'captures', args.dashboard_tls_cert,
                                  args.dashboard_tls_key, args.dashboard_local_trust,
                                  camera, V4L2Camera(f'/dev/video{args.camera}'), profile)
        lines, transactions = Lines(), Transactions(send)
        model_ready = False
        busy = None
        captured = None
        pending = None
        jobs = deque()
        last_display = None
        fatal = None
        started = time.monotonic()
        defaults = StartupDefaults(addon/'station_defaults.json')
        last_ping = 0.0
        event('starting', port=args.port, camera=args.camera, capture_folder=str(audit.folder))
        while not args.run_seconds or time.monotonic()-started < args.run_seconds:
            now = time.monotonic()
            if dashboard and transactions.session is not None and now-last_ping >= .5:
                send(f'PING {transactions.session}')
                last_ping = now
            if not process.is_alive():
                fatal = fatal or 'AI process stopped; restart station'
            if pipe.poll():
                packet = pipe.recv()
                if packet.get('ready'):
                    model_ready = True
                    event('ai_ready', warmup_ms=packet['warmup_ms'], provenance=packet['provenance'])
                elif packet.get('fatal'):
                    fatal = packet['fatal']
                    event('ai_error', reason=fatal)
                else:
                    if busy and tuple(packet['key']) == busy['key']:
                        packet['capture_ms'] = (busy['acked']-busy['requested'])*1000
                        packet['request_to_result_ms'] = (now-busy['requested'])*1000
                        # Deliver result before image encoding, GUI or disk writes.
                        delivered = transactions.finish(busy, packet['result'])
                        packet['ai_result'] = packet['result']
                        packet['result'] = busy.get('sent_result') if delivered else None
                        packet['delivered'] = delivered
                        packet['frame_sequence'] = captured[1]
                        packet['frame_read_started'] = captured[2]
                        packet['frame_read_completed'] = captured[3]
                        last_display = packet.get('displayed', captured[0]).copy()
                        if dashboard:
                            dashboard.inspection(packet, audit.folder.name)
                        audit.submit((busy['key'], captured[0], packet))
                        event('inspection', key=busy['key'], result=packet['result'], reason=packet.get('reason'), delivered=delivered,
                              capture_ms=packet['capture_ms'], total_ms=packet['request_to_result_ms'])
                        busy, captured = None, None
            available = (model_ready and not fatal and not audit.error and camera.healthy()
                         and pending is None and len(transactions.outstanding) < transactions.capacity)
            for line in lines.feed(uart.read(max(1, min(uart.in_waiting, 1024)))):
                device_message = parse_device_line(line)
                if device_message:
                    if dashboard:
                        dashboard.device_line(line)
                    if device_message[0] == 'ack':
                        event('operator_ack', **device_message[1])
                    continue
                event('rx', line=line)
                transaction = transactions.receive(line, available)
                if transaction:
                    pending = (transaction, camera.token())
                # A HELLO may retire an active session; never ACK its old image.
                if pending and transactions.active is not pending[0]:
                    pending = None
                available = available and transactions.active is None
            if dashboard:
                defaults_ready = defaults.tick(dashboard, event)
                dashboard.update_station(
                    ready=available and defaults_ready, camera=camera.healthy(),
                    fault=fatal or audit.error, busy=busy is not None,
                    pending=pending is not None, queue=len(transactions.outstanding),
                    ai_ready=model_ready)
                dashboard.drain(send, transactions.session, event)
            # At most one frame may wait behind the active inference. Holding
            # CAPTURED briefly keeps the incoming box stopped at the camera,
            # instead of filling an eight-image AI queue and timing out later.
            if pending and not jobs and not fatal and not audit.error:
                transaction, sequence = pending
                frame = camera.capture_after(transaction['requested'], sequence)
                if frame is not None:
                    if transactions.captured(transaction):
                        jobs.append((transaction, frame))
                    pending = None
            expired = transactions.expire()
            if expired:
                if pending and pending[0] in expired:
                    pending = None
                fatal = 'capture or AI deadline exceeded; clear conveyor and restart station'
                event('deadline', reason=fatal, keys=[tx['key'] for tx in expired])
            if fatal or audit.error:
                for tx in list(transactions.outstanding.values()):
                    transactions.finish(tx, 'ERROR')
                pending = None
                jobs.clear()
            if not busy and jobs and not fatal and not audit.error:
                while jobs and transactions.outstanding.get(jobs[0][0]['key']) is not jobs[0][0]:
                    jobs.popleft()
                if jobs:
                    busy, captured = jobs.popleft()
                    pipe.send((busy['key'], captured[0]))
            if not args.headless:
                live, _ = camera.read()
                if live is not None:
                    live = cv2.resize(live, (640, 480))
                    status = fatal or audit.error or ('AI READY' if available else 'Loading / inspecting')
                    cv2.rectangle(live, (0, 0), (640, 54), (20, 20, 20), -1)
                    cv2.putText(live, status[:72], (8, 21), cv2.FONT_HERSHEY_SIMPLEX, .48, (255,255,255), 1)
                    cv2.putText(live, 'LIVE | c camera | q quit | motor: ESP console', (8, 44), cv2.FONT_HERSHEY_SIMPLEX, .44, (255,255,255), 1)
                    right = cv2.resize(last_display, (640,480)) if last_display is not None else live*0
                    import numpy as np
                    cv2.imshow('DATN StopGo - Live / Last captured result', np.hstack((live, right)))
                key = cv2.waitKey(1) & 255
                if key == ord('q'):
                    break
                if key == ord('c'):
                    camera.settings()
            time.sleep(.005)
        for tx in list(transactions.outstanding.values()):
            transactions.finish(tx, 'ERROR')
        event('closed', camera_metrics=camera.metrics(), audit_error=audit.error)
        events.close()
    finally:
        if dashboard:
            dashboard.close()
        if uart:
            uart.close()
        if camera:
            camera.close()
        if process:
            process.terminate()
            process.join(timeout=3)
        if audit:
            audit.close()
        cv2.destroyAllWindows()
        lock.close()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Station stopped by operator.', flush=True)
