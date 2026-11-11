from pathlib import Path
import json
import os
import tempfile
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'station'))
from dashboard import Dashboard

with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
    captures = Path(directory)
    folder = captures/'20261111_170000'
    folder.mkdir()
    d = Dashboard('127.0.0.1', 0, 'x'*32, captures, local_trust=True)
    def ready():
        d.device_line('STATE 123 STOPPED 0 1 1 0 0 0 190 0 180 70 60 230 350 350 0')
    def inspect(box, result):
        packet = dict(key=[123, box], result=result, delivered=True,
                      reason='test', request_to_result_ms=100)
        d.inspection(packet, folder.name)
        path = folder/f'123_{box}.json'
        path.write_text(json.dumps(packet))
        stamp = d.recent[0]['at']
        os.utime(path, (stamp, stamp))
    try:
        ready()
        first, error = d.create_run('first')
        assert not error
        inspect(191, 'PASS')
        inspect(192, 'DEFECT')
        snap = d.snapshot()
        assert snap['run_box_count'] == 2 and snap['counts'] == dict(PASS=1, DEFECT=1, ERROR=0)
        assert snap['recent'][0]['run_number'] == 2
        ready()
        second, error = d.create_run('second')
        assert not error
        snap = d.snapshot()
        assert snap['run_box_count'] == 0 and not snap['recent']
        assert snap['counts'] == dict(PASS=0, DEFECT=0, ERROR=0)
        inspect(193, 'DEFECT')
        assert d.snapshot()['recent'][0]['run_number'] == 1
        old = d.run_detail(first['id'])
        assert old['counts'] == dict(PASS=1, DEFECT=1, ERROR=0)
        assert [r['run_number'] for r in old['results']] == [2, 1]
        assert d.run_detail(second['id'])['results'][0]['run_number'] == 1
        assert 'stt_trong_phien' in d.run_export(first['id'], 'csv')[0].decode('utf-8-sig')
    finally:
        d.close()
    restored = Dashboard('127.0.0.1', 0, 'x'*32, captures, local_trust=True)
    try:
        assert restored.snapshot()['run_box_count'] == 1
        assert restored.snapshot()['counts'] == dict(PASS=0, DEFECT=1, ERROR=0)
        inspect_packet = dict(key=[123, 194], result='PASS', delivered=True)
        restored.inspection(inspect_packet, folder.name)
        assert restored.snapshot()['recent'][0]['run_number'] == 2
    finally:
        restored.close()
print('PASS: per-run reset, numbering, preserved history/CSV, restore after restart')
