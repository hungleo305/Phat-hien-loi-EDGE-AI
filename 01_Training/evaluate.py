"""Evaluate trained v4 models on held-out physical boxes and original v4 test.

The 50 new BOX1-5 images are training examples, so they are not included in
the locked accuracy summary. BOX6 and both PASS_KIEMTHU boxes remain unseen.
"""

from collections import Counter, defaultdict
import argparse
import json
from pathlib import Path
import re
import sys

import cv2
from ultralytics import YOLO

ROOT = Path(r"F:\DATN")
BASE = Path(__file__).resolve().parent
OUT = ROOT / "Cong_cu_phat_trien/outputs/newlabel_v4_20261028"
SOURCE = ROOT / "Du_lieu_goc/Dataset_Builder/kiemthu"
OLD_TEST = BASE / "dataset_export/test/images"
SRC = BASE.parent / "label_integrity_20261023/stage/src"
sys.path.insert(0, str(SRC))
from label_verifier import LabelVerifier  # noqa: E402

WHOLE_THRESHOLD = .40
SURFACE_THRESHOLD = .05  # frozen from the pre-v4 evaluation
SURFACE_MAX_AREA_RATIO = .20
INTEGRITY_MARKERS = ("added marks on label", "torn label / exposed cardboard")

parser = argparse.ArgumentParser()
parser.add_argument("--whole", choices=("v4", "v2", "balanced"), default="v4")
parser.add_argument("--surface", choices=("crop", "finetuned", "v3"), default="crop")
parser.add_argument("--test-source", choices=("raw", "export"), default="raw")
parser.add_argument("--integrity-policy", choices=("defect", "review"), default="defect")
args = parser.parse_args()
whole_paths = {
    "v4": OUT / "training/whole_640/weights/best.pt",
    "balanced": OUT / "training/whole_balanced_finetune_640/weights/best.pt",
    "v2": ROOT / "Cong_cu_phat_trien/outputs/newlabel_v2_20261028/training/v2_yolov8n_rotation_640/weights/best.pt",
}
whole_path = whole_paths[args.whole]
surface_paths = {
    "crop": OUT / "training/crop_surface_960/weights/best.pt",
    "finetuned": OUT / "training/surface_finetune_960/weights/best.pt",
    "v3": ROOT / "Cong_cu_phat_trien/outputs/newlabel_v2_20261028/training/v3_surface_combined_960/weights/best.pt",
}
whole_model = YOLO(str(whole_path))
surface_model = YOLO(str(surface_paths[args.surface]))
verifier = LabelVerifier(BASE.parent / "new_label_verifier_20261027/assets/approved_label.png")

records = []
for path in sorted(SOURCE.glob("*.jpg")):
    m = re.match(r"datn_box_(\d+)_", path.name)
    if m and 50 <= int(m.group(1)) < 60:
        records.append(("locked", "BOX6", "DEFECT", path))
        continue
    m = re.match(r"PASS_KIEMTHU(0[12]) \((\d+)\)\.jpg$", path.name, re.I)
    if m:
        records.append(("locked", f"PASS{int(m.group(1)):02d}", "PASS", path))
for path in sorted(OLD_TEST.glob("*.jpg")):
    m = re.match(r"(BOX\d{2}|PASS\d{2})_", path.name)
    if not m:
        raise ValueError(f"Unknown old test group: {path}")
    group = m.group(1)
    truth = "PASS" if group.startswith("PASS") or group in ("BOX01", "BOX02") else "DEFECT"
    if args.test_source == "raw":
        prefix = path.stem.split("_jpg.rf.")[0]
        path = ROOT / "Du_lieu_goc/Dataset_Builder/images" / f"{prefix}.jpg"
        if not path.is_file():
            raise FileNotFoundError(path)
    records.append(("v4_test", group, truth, path))
if Counter(row[0] for row in records) != {"locked": 30, "v4_test": 50}:
    raise ValueError("Expected exactly 30 locked + 50 v4 test images")

whole_results = whole_model.predict(
    source=[str(row[3]) for row in records], imgsz=640, conf=.01, iou=.5,
    batch=4, device=0, verbose=False,
)
rows = []
for (suite, group, truth, path), result in zip(records, whole_results):
    img = cv2.imread(str(path))
    if img is None:
        raise ValueError(f"Unreadable image: {path}")
    candidates = []
    for box in result.boxes:
        cls = int(box.cls.item())
        if cls in (0, 1):
            candidates.append((cls, float(box.conf.item()), [float(v) for v in box.xyxy[0]]))
    defect = [c for c in candidates if c[0] == 0 and c[1] >= WHOLE_THRESHOLD]
    selected = max(defect or candidates, key=lambda c: c[1], default=None)
    surface_score = 0.
    verification = {"status": "not_found", "reason": "no whole box"}
    crop_shape = None
    if selected:
        cls, whole_score, (x1, y1, x2, y2) = selected
        pad = round(max(x2 - x1, y2 - y1) * .04)
        ix1, iy1 = max(0, round(x1) - pad), max(0, round(y1) - pad)
        ix2, iy2 = min(img.shape[1], round(x2) + pad), min(img.shape[0], round(y2) + pad)
        crop = img[iy1:iy2, ix1:ix2]
        if crop.size:
            crop_shape = list(crop.shape[:2])
            surface_source = crop if args.surface == "crop" else img
            surface = surface_model.predict(source=surface_source, imgsz=960, conf=.01,
                                            iou=.5, device=0, verbose=False)[0]
            area = max(1., (x2 - x1) * (y2 - y1))
            local = []
            for box in surface.boxes:
                sx1, sy1, sx2, sy2 = [float(v) for v in box.xyxy[0]]
                ratio = (sx2 - sx1) * (sy2 - sy1) / area
                cx, cy = (sx1 + sx2) / 2, (sy1 + sy2) / 2
                if ratio <= SURFACE_MAX_AREA_RATIO and (
                    args.surface == "crop" or (x1 <= cx <= x2 and y1 <= cy <= y2)
                ):
                    local.append(float(box.conf.item()))
            surface_score = max(local, default=0.)
            verification = verifier.verify(crop)
    reason = verification["reason"].lower()
    whole_gate = bool(selected and selected[0] == 0)
    surface_gate = surface_score >= SURFACE_THRESHOLD
    fields = (verification.get("integrity") or {}).get("critical_fields") or {}
    failed_regions = [name for name in verification.get("failed_regions", [])
                      if name in ("qc", "year")]
    field_gate = bool(failed_regions) or any(
        bool(fields.get(name, {}).get("mismatch")) for name in ("qc", "year")
    )
    field_unconfirmed = any(bool(fields.get(name, {}).get("insufficient")) for name in ("qc", "year"))
    integrity_gate = any(marker in reason for marker in INTEGRITY_MARKERS)
    if selected is None:
        decision = "REVIEW"
    elif any((whole_gate, surface_gate, field_gate)):
        decision = "DEFECT"
    elif field_unconfirmed:
        decision = "REVIEW"
    elif integrity_gate:
        decision = "REVIEW" if args.integrity_policy == "review" else "DEFECT"
    else:
        decision = "PASS"
    rows.append({
        "suite": suite, "group": group, "image": path.name, "truth": truth,
        "decision": decision, "correct": decision == truth,
        "whole_score": round(selected[1], 4) if selected else 0.,
        "surface_score": round(surface_score, 4), "crop_shape": crop_shape,
        "whole_gate": whole_gate, "surface_gate": surface_gate,
        "field_gate": field_gate, "field_unconfirmed": field_unconfirmed,
        "field_failed_regions": failed_regions,
        "integrity_gate": integrity_gate,
        "verifier_status": verification["status"],
        "verifier_reason": verification["reason"],
    })

summary = {
    "models": {"whole": str(whole_path), "surface": str(surface_paths[args.surface]),
               "surface_mode": args.surface, "test_source": args.test_source,
               "integrity_policy": args.integrity_policy},
    "thresholds": {"whole": WHOLE_THRESHOLD, "surface": SURFACE_THRESHOLD,
                   "surface_max_area_ratio": SURFACE_MAX_AREA_RATIO},
    "suites": {}, "rows": rows,
    "caveat": "BOX6 and two PASS boxes were reviewed while developing earlier v3; this is a held-out training test, not a fresh prospective acceptance test.",
}
for suite in ("locked", "v4_test"):
    subset = [r for r in rows if r["suite"] == suite]
    summary["suites"][suite] = {
        "counts": dict(Counter(f"{r['truth']}->{r['decision']}" for r in subset)),
        "by_group": {g: dict(Counter(r["decision"] for r in subset if r["group"] == g))
                     for g in sorted({r["group"] for r in subset})},
        "errors": [r for r in subset if not r["correct"]],
    }
(OUT / f"evaluation_{args.whole}_{args.surface}_{args.test_source}_{args.integrity_policy}_structured.json").write_text(
    json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(json.dumps({suite: {"counts": value["counts"], "by_group": value["by_group"]}
                  for suite, value in summary["suites"].items()}, ensure_ascii=False, indent=2))
