"""Export production checkpoints to isolated NCNN FP16 candidates."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil

PROJECT = Path(__file__).resolve().parents[2]
SOURCE = Path(__file__).resolve().parents[1] / '03_Inference_Pi/runtime/models'
FP16_MARKER = bytes.fromhex('476b3001')  # NCNN little-endian 0x01306B47
MODELS = (('whole_balanced', 640), ('surface_finetuned', 960))

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', type=Path, required=True,
                        help='New work directory under F:\\DATN')
    args = parser.parse_args()
    output = args.output_root.resolve()
    if PROJECT not in output.parents or output.exists():
        parser.error('--output-root must be a new directory inside F:\\DATN')
    output.mkdir(parents=True)
    os.environ['YOLO_CONFIG_DIR'] = str(output / 'yolo_config')
    os.environ['MPLCONFIGDIR'] = str(output / 'mplcache')
    os.environ['YOLO_AUTOINSTALL'] = 'false'
    from ultralytics import YOLO, __version__ as ultralytics_version

    records = []
    for name, imgsz in MODELS:
        checkpoint = SOURCE / f'{name}.pt'
        if not checkpoint.is_file():
            raise FileNotFoundError(checkpoint)
        local_checkpoint = output / checkpoint.name
        shutil.copy2(checkpoint, local_checkpoint)
        exported = Path(YOLO(str(local_checkpoint)).export(
            format='ncnn', imgsz=imgsz, half=True, device='cpu'
        ))
        weight = exported / 'model.ncnn.bin'
        param = exported / 'model.ncnn.param'
        metadata = (exported / 'metadata.yaml').read_text(encoding='utf-8')
        marker_count = weight.read_bytes().count(FP16_MARKER)
        if not param.is_file() or marker_count == 0 or 'half: true' not in metadata:
            raise RuntimeError(f'FP16 export verification failed: {exported}')
        records.append({
            'name': name, 'imgsz': imgsz,
            'source_sha256': sha256(checkpoint),
            'weight_sha256': sha256(weight),
            'weight_bytes': weight.stat().st_size,
            'fp16_marker_count': marker_count,
            'path': str(exported),
        })
    manifest = {
        'ultralytics_version': ultralytics_version,
        'status': 'candidate; Pi replay and timing required before deployment',
        'models': records,
    }
    (output / 'export_manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
