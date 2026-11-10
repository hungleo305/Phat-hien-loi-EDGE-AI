"""Offline integrity and five adjudicated owned-box decisions."""
import argparse
from pathlib import Path
import sys
import cv2

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from integrity import verify
from current_pipeline import CurrentInspection

EXPECTED = {
    "physical_defect.jpg": "DEFECT",
    "qc_failed.jpg": "DEFECT",
    "pass.jpg": "PASS",
    "added_marks.jpg": "DEFECT",
    # Same SHA-256 as PASS13_QC_PASSED_2026_01.jpg, adjudicated PASS.
    "review.jpg": "PASS",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=("ncnn", "torch"), default="ncnn")
    args = parser.parse_args()
    verify(ROOT)
    pipeline = CurrentInspection(ROOT, backend=args.backend)
    pipeline.warmup()
    for name, expected in EXPECTED.items():
        image = cv2.imread(str(ROOT / "samples" / name))
        if image is None:
            raise FileNotFoundError(name)
        result = pipeline.inspect(image)
        print(name, result["decision"], result["reason"], result["processing_ms"])
        if result["decision"] != expected:
            raise RuntimeError(f"{name}: {expected} != {result['decision']}")
    print("SELF CHECK PASSED 5/5")


if __name__ == "__main__":
    main()
