"""Fine-tune either production model into a new, isolated output directory."""
import argparse
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PROJECT = REPO.parent

def main(default_model='whole'):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', choices=('whole', 'surface'), default=default_model)
    parser.add_argument('--data', type=Path, help='YOLO dataset YAML')
    parser.add_argument('--weights', type=Path, help='Initial checkpoint; no automatic download')
    parser.add_argument('--output', type=Path, required=True, help='New output directory inside F:/DATN')
    parser.add_argument('--device', default='0', help='Ultralytics device, e.g. 0 or cpu')
    args = parser.parse_args()
    surface = args.model == 'surface'
    dataset = 'dataset_surface_combined' if surface else 'dataset_detection_balanced'
    data = args.data or PROJECT/'Du_lieu_goc/Huan_luyen'/dataset/'data.yaml'
    weights = args.weights or PROJECT/'Du_lieu_goc/Huan_luyen/initial_weights'/('surface_initial.pt' if surface else 'whole_initial.pt')
    output = args.output.resolve()
    if output.exists() or not output.is_relative_to(PROJECT):
        parser.error('--output must be a new directory inside the project workspace')
    for path in [data, weights]:
        if not path.is_file():
            parser.error(f'Missing input: {path}; supply --data / --weights')
    import os
    settings = Path(__file__).resolve().parent / 'runtime_settings'
    (settings / 'Ultralytics').mkdir(parents=True, exist_ok=True)
    os.environ['YOLO_CONFIG_DIR'] = str(settings)
    os.environ['YOLO_AUTOINSTALL'] = 'false'
    from ultralytics import YOLO
    YOLO(str(weights)).train(
        data=str(data), epochs=25, patience=8, imgsz=960 if surface else 640,
        batch=2 if surface else 4, device=args.device, workers=0, seed=24,
        deterministic=True, project=str(output.parent), name=output.name,
        exist_ok=False, plots=True, optimizer='AdamW', lr0=.001, lrf=.01,
        weight_decay=.0005, cos_lr=False, degrees=180, translate=.04, scale=.10,
        shear=0, perspective=0, flipud=0, fliplr=0, mosaic=0, mixup=0,
        copy_paste=0, hsv_h=0, hsv_s=.05, hsv_v=.12)

if __name__ == '__main__':
    main()
