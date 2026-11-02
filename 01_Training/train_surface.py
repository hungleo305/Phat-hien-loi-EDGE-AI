"""Adapt the v3 surface detector to v4 corrected physical-defect labels."""

import json
from pathlib import Path

import torch
from ultralytics import YOLO

ROOT = Path(r"F:\DATN")
BASE = Path(__file__).resolve().parent
DATA = BASE / "dataset_surface_combined/data.yaml"
PRETRAIN = ROOT / "Cong_cu_phat_trien/outputs/newlabel_v2_20261028/training/v3_surface_combined_960/weights/best.pt"
PROJECT = ROOT / "Cong_cu_phat_trien/outputs/newlabel_v4_20261028/training"
RUN = PROJECT / "surface_finetune_960"
if not torch.cuda.is_available() or not PRETRAIN.is_file():
    raise SystemExit("CUDA or v3 surface checkpoint unavailable")
if RUN.exists():
    raise SystemExit(f"Output already exists: {RUN}")

YOLO(str(PRETRAIN)).train(
    data=str(DATA), epochs=25, patience=8, imgsz=960, batch=2,
    device=0, workers=0, seed=24, deterministic=True,
    project=str(PROJECT), name=RUN.name, exist_ok=False, plots=False,
    optimizer="AdamW", lr0=.001, lrf=.01,
    degrees=180, translate=.04, scale=.10, shear=0, perspective=0,
    flipud=0, fliplr=0, mosaic=0, mixup=0, copy_paste=0,
    hsv_h=0, hsv_s=.05, hsv_v=.12,
)
best = RUN / "weights/best.pt"
if not best.is_file():
    raise FileNotFoundError(best)
metrics = YOLO(str(best)).val(
    data=str(DATA), split="val", imgsz=960, batch=2, device=0,
    workers=0, plots=False, project=str(RUN), name="valid_evaluation", exist_ok=False,
)
summary = {
    "model": str(best), "pretrained": str(PRETRAIN), "dataset": str(DATA),
    "validation": {key: float(value) for key, value in metrics.results_dict.items()},
}
(RUN / "metrics_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print("FINETUNE_COMPLETE", best)
