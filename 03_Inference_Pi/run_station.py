"""Launch the station with this repository runtime and camera profile."""
from pathlib import Path
import runpy
import sys

def main():
    root = Path(__file__).resolve().parent
    station = root.parent / '05_Dashboard/station'
    sys.path.insert(0, str(station))
    if '--root' not in sys.argv:
        sys.argv.extend(['--root', str(root / 'runtime')])
    runpy.run_path(str(station / 'run_station.py'), run_name='__main__')

if __name__ == '__main__':
    main()
