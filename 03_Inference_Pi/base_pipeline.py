"""Frozen Pi runtime for the 29/10/2026 whole+surface+field pipeline."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import time

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent / "runtime"
os.environ.setdefault("YOLO_CONFIG_DIR", str(ROOT / "runs" / "yolo_config"))
from ultralytics import YOLO

from label_verifier import LabelVerifier


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


class CurrentInspection:
    """Return PASS, DEFECT or REVIEW without temporal state from earlier boxes."""

    def __init__(self, root: Path = ROOT, backend: str | None = None, threads: int | None = None):
        self.root = Path(root).resolve()
        self.config = json.loads((self.root / "config/app.json").read_text(encoding="utf-8"))
        self.backend = backend or self.config["whole_backend"]
        if self.backend not in ("ncnn", "torch"):
            raise ValueError("backend must be ncnn or torch")
        self.threads = int(threads or self.config["torch_threads"])
        cv2.setNumThreads(int(self.config["opencv_threads"]))
        os.environ.setdefault("YOLO_AUTOINSTALL", "false")
        os.environ.setdefault("OMP_WAIT_POLICY", "PASSIVE")
        if self.backend == "torch":
            import torch
            torch.set_num_threads(self.threads)
            whole_path = self.root / "models/whole_balanced.pt"
            surface_path = self.root / "models/surface_finetuned.pt"
            self.device = "cpu"
        else:
            whole_path = self.root / "models/whole_balanced_ncnn_model"
            surface_path = self.root / "models/surface_finetuned_ncnn_model"
            self.device = None
        required = [whole_path, surface_path, self.root / "assets/approved_label.png"]
        missing = [str(path) for path in required if not path.exists()]
        if missing:
            raise FileNotFoundError("Missing runtime files: " + ", ".join(missing))
        self.whole_model = YOLO(str(whole_path), task="detect")
        self.surface_model = YOLO(str(surface_path), task="detect")
        self.verifier = LabelVerifier(self.root / "assets/approved_label.png")
        self.whole_imgsz = int(self.config["whole_imgsz"])
        self.surface_imgsz = int(self.config["surface_imgsz"])
        self.whole_threshold = float(self.config["whole_threshold"])
        self.surface_threshold = float(self.config["surface_threshold"])
        # Trial override: restore the validated RC surface gate. The live Pi
        # config was changed to 0.20, which misses real marks at 0.1984/0.1308.
        self.surface_threshold = 0.05
        self.surface_max_area_ratio = float(self.config["surface_max_area_ratio"])
        tracked = [self.root / "config/app.json", self.root / "assets/approved_label.png"]
        tracked += sorted(path for path in (self.root / "models").rglob("*") if path.is_file())
        self.provenance = {
            "release": self.config["release"],
            "backend": self.backend,
            "threads": self.threads,
            "files_sha256": {str(path.relative_to(self.root)): digest(path) for path in tracked},
        }

    @staticmethod
    def _class_name(model: YOLO, class_id: int) -> str:
        names = model.names
        return str(names[class_id] if isinstance(names, dict) else names[class_id])

    def _predict(self, model: YOLO, image, imgsz: int):
        arguments = dict(imgsz=imgsz, conf=0.01, iou=0.5, verbose=False)
        if self.device is not None:
            arguments["device"] = self.device
        return model.predict(image, **arguments)[0]

    def warmup(self) -> float:
        started = time.perf_counter()
        blank = np.zeros((480, 640, 3), dtype=np.uint8)
        self._predict(self.whole_model, blank, self.whole_imgsz)
        self._predict(self.surface_model, blank, self.surface_imgsz)
        return (time.perf_counter() - started) * 1000

    def inspect(self, image):
        started = time.perf_counter()
        whole_result = self._predict(self.whole_model, image, self.whole_imgsz)
        whole_finished = time.perf_counter()
        candidates = []
        for box in whole_result.boxes:
            name = self._class_name(self.whole_model, int(box.cls.item())).upper()
            if name in ("PASS", "DEFECT"):
                candidates.append({
                    "name": name,
                    "score": float(box.conf.item()),
                    "xyxy": [float(value) for value in box.xyxy[0]],
                })
        defect_candidates = [
            item for item in candidates
            if item["name"] == "DEFECT" and item["score"] >= self.whole_threshold
        ]
        selected = max(defect_candidates or candidates, key=lambda item: item["score"], default=None)
        whole_gate = bool(selected and selected["name"] == "DEFECT"
                          and selected["score"] >= self.whole_threshold)
        surface_boxes = []
        surface_score = 0.0
        verification = {"status": "not_found", "reason": "no whole box"}
        verification_origin = (0, 0)
        surface_finished = whole_finished
        verifier_finished = whole_finished
        if selected is not None and not whole_gate:
            x1, y1, x2, y2 = selected["xyxy"]
            pad = round(max(x2 - x1, y2 - y1) * 0.30)
            ix1, iy1 = max(0, round(x1) - pad), max(0, round(y1) - pad)
            ix2 = min(image.shape[1], round(x2) + pad)
            iy2 = min(image.shape[0], round(y2) + pad)
            crop = image[iy1:iy2, ix1:ix2]
            if crop.size:
                surface_result = self._predict(self.surface_model, image, self.surface_imgsz)
                whole_area = max(1.0, (x2 - x1) * (y2 - y1))
                for box in surface_result.boxes:
                    sx1, sy1, sx2, sy2 = [float(value) for value in box.xyxy[0]]
                    ratio = (sx2 - sx1) * (sy2 - sy1) / whole_area
                    cx, cy = (sx1 + sx2) / 2, (sy1 + sy2) / 2
                    score = float(box.conf.item())
                    if ratio <= self.surface_max_area_ratio and x1 <= cx <= x2 and y1 <= cy <= y2:
                        surface_boxes.append({"score": score, "xyxy": [sx1, sy1, sx2, sy2]})
                surface_score = max((item["score"] for item in surface_boxes), default=0.0)
                surface_finished = time.perf_counter()
                # Once a physical defect has crossed the fail threshold, OCR/
                # template verification cannot change the final DEFECT result.
                if surface_score < self.surface_threshold:
                    verification = self.verifier.verify(crop)
                    verification_origin = (ix1, iy1)
                    # Trial: a larger ROI should cover rotated label edges.
                    # Run the full-frame verifier only when the ROI does not
                    # establish a clear decision; validate against held-out
                    # physical marks and 2025 year mismatches before use.
                    if verification.get("status") in ("mismatch", "not_found", "insufficient_detail"):
                        full_verification = self.verifier.verify(image)
                        for _ in range(2):
                            if full_verification.get("status") not in ("not_found", "insufficient_detail"):
                                break
                            retry = self.verifier.verify(image)
                            if retry.get("status") in ("verified", "mismatch"):
                                full_verification = retry
                                break
                        full_fields = ((full_verification.get("integrity") or {})
                                       .get("critical_fields") or {})
                        full_critical = any(
                            bool(full_fields.get(name, {}).get("mismatch"))
                            for name in ("qc", "year")) or any(
                            name in ("qc", "year")
                            for name in full_verification.get("failed_regions", []))
                        if (verification.get("status") in ("not_found", "insufficient_detail") or
                                full_critical or
                                (verification.get("status") == "verified" and
                                 full_verification.get("status") != "verified") or
                                (verification.get("status") == "mismatch" and
                                 full_verification.get("status") in ("not_found", "insufficient_detail"))):
                            verification = full_verification
                            verification_origin = (0, 0)
                    verifier_finished = time.perf_counter()
                else:
                    verifier_finished = surface_finished
        surface_gate = surface_score >= self.surface_threshold
        fields = (verification.get("integrity") or {}).get("critical_fields") or {}
        failed_regions = [name for name in verification.get("failed_regions", [])
                          if name in ("qc", "year")]
        field_gate = bool(failed_regions) or any(
            bool(fields.get(name, {}).get("mismatch")) for name in ("qc", "year")
        )
        field_unconfirmed = any(
            bool(fields.get(name, {}).get("insufficient")) for name in ("qc", "year")
        )
        verifier_reason = str(verification.get("reason", "")).lower()
        added_marks_gate = "added marks on label" in verifier_reason
        torn_exposed_gate = "torn label / exposed cardboard" in verifier_reason
        if selected is None:
            decision, reason = "REVIEW", "whole box not found"
        elif whole_gate:
            decision, reason = "DEFECT", "whole-box model"
        elif surface_gate:
            decision, reason = "DEFECT", "visible physical defect"
        elif field_gate:
            decision, reason = "DEFECT", "QC/year mismatch"
        elif added_marks_gate:
            decision, reason = "DEFECT", "visible marks/damage on label"
        elif field_unconfirmed:
            decision, reason = "REVIEW", "QC/year not confirmed"
        elif torn_exposed_gate:
            decision, reason = "REVIEW", str(verification.get("reason", "label integrity"))
        elif verification.get("status") in ("not_found", "insufficient_detail"):
            decision, reason = "REVIEW", f"label {verification.get('status')}: {verification.get('reason', '')}"
        else:
            decision, reason = "PASS", "all active checks passed"
        return {
            "decision": decision,
            "reason": reason,
            "processing_ms": round((time.perf_counter() - started) * 1000, 1),
            "timing_ms": {
                "whole": round((whole_finished - started) * 1000, 1),
                "surface": round((surface_finished - whole_finished) * 1000, 1),
                "verifier": round((verifier_finished - surface_finished) * 1000, 1),
            },
            "whole": selected,
            "surface_score": round(surface_score, 4),
            "surface_boxes": surface_boxes,
            "whole_gate": whole_gate,
            "surface_gate": surface_gate,
            "field_gate": field_gate,
            "field_unconfirmed": field_unconfirmed,
            "field_failed_regions": failed_regions,
            "added_marks_gate": added_marks_gate,
            "torn_exposed_gate": torn_exposed_gate,
            "verifier_status": verification.get("status", "not_found"),
            "verifier_reason": verification.get("reason", ""),
            "label_corners": [
                [round(point[0] + verification_origin[0], 1),
                 round(point[1] + verification_origin[1], 1)]
                for point in verification.get("label_corners_in_crop", [])
            ],
            "backend": self.backend,
        }

    def annotate(self, image, result):
        canvas = image.copy()
        colors = {"PASS": (0, 190, 0), "DEFECT": (0, 0, 255), "REVIEW": (0, 200, 255)}
        color = colors[result["decision"]]
        whole = result.get("whole")
        if whole and whole["score"] >= self.whole_threshold:
            x1, y1, x2, y2 = [round(value) for value in whole["xyxy"]]
            cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 3)
        corners = result.get("label_corners", [])
        if len(corners) == 4:
            cv2.polylines(canvas, [np.rint(corners).astype(np.int32)], True,
                          color if result.get("verifier_status") == "verified" else (0, 200, 255), 2)
        active = [item for item in result.get("surface_boxes", [])
                  if item["score"] >= self.surface_threshold]
        if active:
            item = max(active, key=lambda candidate: candidate["score"])
            x1, y1, x2, y2 = [round(value) for value in item["xyxy"]]
            cv2.rectangle(canvas, (x1, y1), (x2, y2), (255, 120, 0), 2)
        text = f"{result['decision']} | {result['reason']} | {result['processing_ms']:.0f} ms"
        cv2.rectangle(canvas, (0, 0), (canvas.shape[1], 58), (10, 10, 10), -1)
        cv2.putText(canvas, text, (12, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.58, color, 2)
        if whole and whole["score"] < self.whole_threshold:
            note = f"Whole-box bbox uncertain ({whole['score']:.2f}); outline = label"
            cv2.putText(canvas, note, (12, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.46,
                        (0, 200, 255), 1)
        return canvas
