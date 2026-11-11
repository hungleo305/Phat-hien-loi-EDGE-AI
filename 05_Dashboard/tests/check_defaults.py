from pathlib import Path
import threading
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'station'))
from startup_defaults import StartupDefaults


class Dashboard:
    def __init__(self):
        self.lock = threading.Lock()
        self.device = dict(session=1, motor_speed=160, light_level=30,
                           servo_angle=35, servo_hold=350, servo_moving=False)
        self.operations = {}
        self.clear = True
        self.sent = []

    def _fresh_device(self):
        return self.device

    def _stopped_clear(self, device):
        return self.clear

    def submit(self, verb, value):
        sequence = len(self.sent) + 1
        self.sent.append((verb, value))
        self.operations[sequence] = {'state': 'sent'}
        return sequence, None


d = Dashboard()
s = StartupDefaults(Path(__file__).resolve().parents[1]/'station/station_defaults.json')
events = []
def event(name, **fields):
    events.append(name)

d.clear = False
assert not s.tick(d, event) and not d.sent
d.clear = True
for verb, field, value in s.targets:
    s.next_attempt = 0
    if d.device[field] != value:
        assert not s.tick(d, event)
        assert d.sent[-1] == (verb, value)
        count = len(d.sent)
        assert not s.tick(d, event) and len(d.sent) == count
        d.operations[s.pending]['state'] = 'accepted'
        d.device[field] = value
        s.tick(d, event)
s.next_attempt = 0
assert s.tick(d, event)
# Operator adjustments remain intact after initial configuration.
d.device['servo_angle'] = 55
assert s.tick(d, event) and d.device['servo_angle'] == 55
# ESP reset re-arms configuration but cannot configure a running machine.
d.device['session'] = 2
d.clear = False
assert not s.tick(d, event)
d.clear = True
assert not s.tick(d, event) and d.sent[-1] == ('SERVO_ANGLE', 60)
print('PASS: stopped-only restoration, ACK wait, verify state, preserve operator changes, ESP reset')
