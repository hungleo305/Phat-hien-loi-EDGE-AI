"""Restore operator-approved defaults once per station start/ESP32 session."""
import json
import time


class StartupDefaults:
    def __init__(self, path):
        config = json.loads(path.read_text(encoding='utf-8'))
        expected = {'SPEED': ('motor_speed', 1, 255),
                    'LIGHT': ('light_level', 0, 255),
                    'SERVO_ANGLE': ('servo_angle', 1, 90),
                    'SERVO_HOLD': ('servo_hold', 150, 1500)}
        if set(config) != set(expected):
            raise ValueError('Invalid startup defaults keys')
        self.targets = []
        for verb, (field, low, high) in expected.items():
            value = config[verb]
            if type(value) is not int or not low <= value <= high:
                raise ValueError('Invalid startup default: ' + verb)
            self.targets.append((verb, field, value))
        self.session = None
        self.complete = False
        self.pending = None
        self.next_attempt = 0.0

    def tick(self, dashboard, event):
        now = time.monotonic()
        with dashboard.lock:
            device = dashboard._fresh_device()
            if not device:
                return False
            device = dict(device)
            clear = dashboard._stopped_clear(device) and not device.get('servo_moving')
            if self.session != device['session']:
                self.session = device['session']
                self.complete = False
                self.pending = None
                self.next_attempt = 0.0
                event('startup_defaults_waiting', session=self.session)
            if self.complete:
                return True
            if self.pending:
                operation = dashboard.operations.get(self.pending)
                if operation and operation['state'] in ('queued', 'sent'):
                    return False
                self.pending = None
                self.next_attempt = now + 0.5
        if not clear or now < self.next_attempt:
            return False
        for verb, field, value in self.targets:
            if device.get(field) == value:
                continue
            # Unsupported firmware must never silently count as configured.
            if device.get(field) is None:
                return False
            sequence, error = dashboard.submit(verb, value)
            self.next_attempt = now + 1.0
            if sequence:
                self.pending = sequence
                event('startup_default_queued', session=self.session,
                      verb=verb, value=value, sequence=sequence)
            elif error:
                event('startup_default_deferred', reason=error)
            return False
        self.complete = True
        event('startup_defaults_applied', session=self.session,
              values={verb: value for verb, _, value in self.targets})
        return True
