"""Measure detector metrics; this does not measure final inspection accuracy."""
import argparse
from pathlib import Path
import json, os

def main():
    project = Path(__file__).resolve().parents[2]
    runtime = Path(__file__).resolve().parents[1]/'03_Inference_Pi/runtime'
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', choices=('whole', 'surface'), default='whole')
    parser.add_argument('--data', type=Path)
    parser.add_argument('--weights', type=Path)
    parser.add_argument('--split', choices=('train', 'val', 'test'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--device', default='cpu')
    args = parser.parse_args()
    surface = args.model == 'surface'
    dataset = 'dataset_surface_combined' if surface else 'dataset_detection_balanced'
    data = args.data or project/'Du_lieu_goc/Huan_luyen'/dataset/'data.yaml'
    weights = args.weights or runtime/'models'/('surface_finetuned.pt' if surface else 'whole_balanced.pt')
    output = args.output.resolve()
    if output.exists() or not output.is_relative_to(project):
        parser.error('--output must be a new directory inside the workspace')
    for path in [data, weights]:
        if not path.is_file():parser.error(f'Missing input: {path}')
    settings = Path(__file__).resolve().parent / 'runtime_settings'
    (settings / 'Ultralytics').mkdir(parents=True, exist_ok=True)
    os.environ['YOLO_CONFIG_DIR'] = str(settings)
    os.environ['YOLO_AUTOINSTALL'] = 'false'
    from ultralytics import YOLO
    metrics = YOLO(str(weights)).val(
        data=str(data), split=args.split or ('val' if surface else 'test'),
        imgsz=960 if surface else 640, batch=2 if surface else 4,
        device=args.device, workers=0, plots=True,
        project=str(output.parent), name=output.name, exist_ok=False)
    (output/'metrics_summary.json').write_text(json.dumps({
        'model':str(weights), 'dataset':str(data),
        'split':args.split or ('val' if surface else 'test'),
        'metrics':{k:float(v) for k,v in metrics.results_dict.items()}
    },indent=2),encoding='utf-8')

if __name__ == '__main__':main()
