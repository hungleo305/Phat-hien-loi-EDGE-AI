"""Launch the repository station against the synchronized runtime."""
from pathlib import Path
import runpy,sys
root=Path(__file__).resolve().parent
station=root.parent/'05_Dashboard/station'
sys.path.insert(0,str(station))
if '--root' not in sys.argv:sys.argv.extend(['--root',str(root/'runtime')])
if __name__=='__main__':runpy.run_path(str(station/'run_station.py'),run_name='__main__')
