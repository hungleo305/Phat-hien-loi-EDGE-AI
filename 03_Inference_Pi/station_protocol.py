"""Protocol v1 and transaction ownership; no camera/model dependencies."""
import re
import time


class Lines:
    def __init__(self):
        self.data = bytearray()
        self.discard = False

    def feed(self, chunk):
        for byte in chunk:
            if byte == 10:
                raw = bytes(self.data)
                if raw.endswith(b'\r'):
                    raw = raw[:-1]
                if not self.discard and raw and all(32 <= x <= 126 for x in raw):
                    yield raw.decode('ascii')
                self.data.clear()
                self.discard = False
            elif len(self.data) >= 127 or byte not in range(32, 127) and byte != 13:
                self.discard = True
            elif not self.discard:
                self.data.append(byte)


def parse(line):
    match = re.fullmatch(r'(HELLO|CAPTURE) ([0-9]{1,10}) ([0-9]{1,10})', line)
    if not match:
        return None
    kind, session, value = match.groups()
    session, value = int(session), int(value)
    if max(session, value) > 0xffffffff or kind == 'HELLO' and value != 1:
        return None
    return kind, session, value


def classify(record, shape, sensor_confirmed=False):
    """Classify one capture; an ESP sensor trigger can reject a YOLO miss."""
    boxes = record.get('boxes') or []
    if record.get('error'):
        return 'ERROR', 'inspection failed'
    if not boxes and sensor_confirmed:
        # CAPTURE is issued only after the ESP camera sensor sees an object.
        # A visually unfamiliar, dark box may be missed by YOLO; never let
        # that miss become PASS or stop the line as a model error.
        return 'DEFECT', 'sensor-confirmed object not detected by YOLO'
    if len(boxes) != 1:
        # The chamber sensor confirms that this transaction contains a physical
        # item. Multiple visual candidates are unsafe to pass, but they are a
        # classification outcome rather than a Pi/runtime failure.
        return 'DEFECT', 'unexpected box count in sensor-confirmed capture'
    row = boxes[0]
    if row.get('error') or row.get('decision_ready') is False:
        return 'DEFECT', 'inspection incomplete; fail-safe reject'
    try:
        x1, y1, x2, y2 = row['bbox']
        height, width = shape[:2]
        valid_box = 0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height
        if not valid_box:
            return 'ERROR', 'invalid bounding box'
    except (KeyError, TypeError, ValueError):
        return 'ERROR', 'invalid bounding box'
    if row.get('decision') == 'box_defect':
        return 'DEFECT', row.get('decision_reason', 'defect')
    if (row.get('decision') == 'box_pass' and row.get('yolo_class') == 'box_pass'
            and row.get('label_check', {}).get('verified') is True):
        # The capture sensor naturally stops some boxes close to the lower
        # frame edge.  A verified four-corner label plus the complete detector
        # decision remains valid; edge contact alone must not fault the line.
        return 'PASS', 'appearance and approved label verified'
    return 'DEFECT', 'unexpected or unverified decision; fail-safe reject'


class Transactions:
    def __init__(self, send, now=time.monotonic):
        self.send, self.now = send, now
        self.session = None
        self.retired = set()
        self.last_id = -1
        self.active = None
        self.outstanding = {}
        self.capacity = 8
        self.ack_ms = 1400
        self.result_ms = 4300

    def receive(self, line, available):
        message = parse(line)
        if message is None:
            return None
        kind, session, value = message
        if kind == 'HELLO':
            if session in self.retired:
                return None
            if session != self.session:
                if self.session is not None:
                    self.retired.add(self.session)
                self.session, self.last_id, self.active = session, -1, None
                self.outstanding.clear()
            if available and self.active is None and len(self.outstanding) < self.capacity:
                self.send(f'READY {session}')
            return None
        if session != self.session or value <= self.last_id:
            return None
        self.last_id = value
        if self.active is not None or len(self.outstanding) >= self.capacity or not available:
            self.send(f'RESULT {session} {value} ERROR')
            return None
        self.active = {'key': (session, value), 'requested': self.now(), 'acked': None}
        self.outstanding[self.active['key']] = self.active
        return self.active

    def captured(self, transaction):
        if self.active is not transaction:
            return False
        if (self.now()-transaction['requested'])*1000 >= self.ack_ms:
            self.finish(transaction, 'ERROR')
            return False
        self.send('CAPTURED %s %s' % transaction['key'])
        transaction['acked'] = self.now()
        self.active = None
        return True

    def finish(self, transaction, result):
        if self.outstanding.get(transaction['key']) is not transaction:
            return False
        acked = transaction['acked']
        if result not in ('PASS', 'DEFECT', 'ERROR') or acked is None:
            result = 'ERROR'
        if acked is not None and (self.now()-acked)*1000 >= self.result_ms:
            result = 'ERROR'
        self.send('RESULT %s %s %s' % (*transaction['key'], result))
        transaction['sent_result'] = result
        self.outstanding.pop(transaction['key'])
        if self.active is transaction:
            self.active = None
        return True

    def expire(self):
        expired = []
        for transaction in list(self.outstanding.values()):
            start = transaction['acked'] if transaction['acked'] is not None else transaction['requested']
            limit = self.result_ms if transaction['acked'] is not None else self.ack_ms
            if (self.now()-start)*1000 >= limit:
                self.finish(transaction, 'ERROR')
                expired.append(transaction)
        return expired
