"""Single-pass early-exit inspection runtime with logo suppression and flexible guard."""
from __future__ import annotations

import time
import cv2
import numpy as np

from base_pipeline import CurrentInspection as BaseInspection
from guard_logic import apply_guard


def get_exact_logo_polygon(verifier, v, origin):
    corners = v.get("label_corners_in_crop")
    if not corners or len(corners) != 4:
        return None
    tpl_corners = np.float32([[0, 0], [verifier.size - 1, 0], [verifier.size - 1, verifier.size - 1], [0, verifier.size - 1]])
    crop_corners = np.float32(corners)
    H, _ = cv2.findHomography(tpl_corners, crop_corners)
    if H is None:
        return None
    lx1, ly1, lx2, ly2 = [round(val * verifier.size) for val in verifier.REGIONS['logo']]
    logo_tpl = np.float32([[[lx1, ly1]], [[lx2, ly1]], [[lx2, ly2]], [[lx1, ly2]]])
    logo_in_crop = cv2.perspectiveTransform(logo_tpl, H).squeeze()
    logo_in_img = logo_in_crop + np.array(origin, dtype=np.float32)
    return logo_in_img.astype(np.float32)


class CurrentInspection(BaseInspection):
    """Optimized Single-Pass & Early-Exit pipeline for Pi 4 Stop&Go station."""

    def inspect(self, image):
        started = time.perf_counter()
        timing_ms = {}

        # ---------------------------------------------------------------------
        # Step 1: Whole-box Detection (NCNN 640x640)
        # ---------------------------------------------------------------------
        t_w0 = time.perf_counter()
        whole_result = self._predict(self.whole_model, image, self.whole_imgsz)
        timing_ms["whole"] = round((time.perf_counter() - t_w0) * 1000, 1)

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
        whole_gate = bool(selected and selected["name"] == "DEFECT" and selected["score"] >= self.whole_threshold)

        # Early-Exit 1: Whole box has severe structural defect
        if whole_gate:
            res = {
                "decision": "DEFECT",
                "reason": "whole-box model",
                "processing_ms": round((time.perf_counter() - started) * 1000, 1),
                "timing_ms": {
                    "whole": timing_ms["whole"],
                    "surface": 0.0,
                    "verifier": 0.0,
                },
                "whole": selected,
                "surface_score": 0.0,
                "surface_boxes": [],
                "whole_gate": True,
                "surface_gate": False,
                "field_gate": False,
                "field_unconfirmed": False,
                "field_failed_regions": [],
                "added_marks_gate": False,
                "torn_exposed_gate": False,
                "verifier_status": "not_run",
                "verifier_reason": "whole-box model",
                "label_corners": [],
                "backend": self.backend,
            }
            return apply_guard(image, res)

        # ---------------------------------------------------------------------
        # Step 2: Single-Pass Label Verification (ROI Crop with Full-Frame fallback)
        # ---------------------------------------------------------------------
        t_v0 = time.perf_counter()
        crop = None
        origin = (0, 0)
        if selected is not None:
            x1, y1, x2, y2 = selected["xyxy"]
            pad = round(max(x2 - x1, y2 - y1) * 0.30)
            ix1, iy1 = max(0, round(x1) - pad), max(0, round(y1) - pad)
            ix2 = min(image.shape[1], round(x2) + pad)
            iy2 = min(image.shape[0], round(y2) + pad)
            crop = image[iy1:iy2, ix1:ix2]
            origin = (ix1, iy1)

        v = self.verifier.verify(crop) if (crop is not None and crop.size) else {"status": "not_found"}
        v_reason = str(v.get("reason", ""))

        # Fallback to full-frame if crop is not found, insufficient, or hit border-crop artifact / logo difference
        if v.get("status") in ("not_found", "insufficient_detail") or "torn label" in v_reason or "differs in logo" in v_reason:
            v_full = self.verifier.verify(image)
            if v_full.get("status") == "verified":
                v = v_full
                origin = (0, 0)
            elif v.get("status") in ("not_found", "insufficient_detail") and v_full.get("status") in ("verified", "mismatch"):
                v = v_full
                origin = (0, 0)
            elif "differs in logo" in v_reason and "differs in logo" not in str(v_full.get("reason", "")):
                v = v_full
                origin = (0, 0)

        timing_ms["verifier"] = round((time.perf_counter() - t_v0) * 1000, 1)

        v_status = v.get("status", "not_found")
        v_reason = str(v.get("reason", ""))

        # Evaluate critical fields and integrity
        fields = (v.get("integrity") or {}).get("critical_fields") or {}
        failed_critical = [r for r in v.get("failed_regions", []) if r in ("qc", "year")]
        field_gate = bool(failed_critical) or any(bool(fields.get(name, {}).get("mismatch")) for name in ("qc", "year"))
        field_unconfirmed = any(bool(fields.get(name, {}).get("insufficient")) for name in ("qc", "year"))
        added_marks_gate = "added marks on label" in v_reason
        torn_exposed_gate = "torn label / exposed cardboard" in v_reason

        # Case 2A: No whole box AND no label found -> REVIEW
        if selected is None and v_status in ("not_found", "insufficient_detail"):
            res = {
                "decision": "REVIEW",
                "reason": f"whole box not found / label {v_status}",
                "processing_ms": round((time.perf_counter() - started) * 1000, 1),
                "timing_ms": {
                    "whole": timing_ms["whole"],
                    "surface": 0.0,
                    "verifier": timing_ms["verifier"],
                },
                "whole": None,
                "surface_score": 0.0,
                "surface_boxes": [],
                "whole_gate": False,
                "surface_gate": False,
                "field_gate": False,
                "field_unconfirmed": False,
                "field_failed_regions": [],
                "added_marks_gate": False,
                "torn_exposed_gate": False,
                "verifier_status": v_status,
                "verifier_reason": v_reason,
                "label_corners": [],
                "backend": self.backend,
            }
            return apply_guard(image, res)

        # Early-Exit 2B: Detected box without label -> DEFECT (route/reject box, do NOT stop conveyor!)
        if v_status == "not_found":
            res = {
                "decision": "DEFECT",
                "reason": "missing label on detected cardboard box",
                "processing_ms": round((time.perf_counter() - started) * 1000, 1),
                "timing_ms": {
                    "whole": timing_ms["whole"],
                    "surface": 0.0,
                    "verifier": timing_ms["verifier"],
                },
                "whole": selected,
                "surface_score": 0.0,
                "surface_boxes": [],
                "whole_gate": False,
                "surface_gate": False,
                "field_gate": False,
                "field_unconfirmed": False,
                "field_failed_regions": [],
                "added_marks_gate": False,
                "torn_exposed_gate": False,
                "verifier_status": "not_found",
                "verifier_reason": "missing label",
                "label_corners": [],
                "backend": self.backend,
            }
            return apply_guard(image, res)

        # Early-Exit 2C: Critical Field Mismatch (wrong year 2025 or QC FAILED)
        if field_gate:
            corners = []
            if v.get("label_corners_in_crop"):
                corners = (np.array(v["label_corners_in_crop"]) + np.array(origin)).tolist()
            res = {
                "decision": "DEFECT",
                "reason": "QC/year mismatch",
                "processing_ms": round((time.perf_counter() - started) * 1000, 1),
                "timing_ms": {
                    "whole": timing_ms["whole"],
                    "surface": 0.0,
                    "verifier": timing_ms["verifier"],
                },
                "whole": selected,
                "surface_score": 0.0,
                "surface_boxes": [],
                "whole_gate": False,
                "surface_gate": False,
                "field_gate": True,
                "field_unconfirmed": False,
                "field_failed_regions": failed_critical,
                "added_marks_gate": False,
                "torn_exposed_gate": False,
                "verifier_status": "mismatch",
                "verifier_reason": v_reason,
                "label_corners": corners,
                "backend": self.backend,
            }
            return apply_guard(image, res)

        # Early-Exit 2D: Added marks / damage on label
        if added_marks_gate:
            corners = []
            if v.get("label_corners_in_crop"):
                corners = (np.array(v["label_corners_in_crop"]) + np.array(origin)).tolist()
            res = {
                "decision": "DEFECT",
                "reason": "visible marks/damage on label",
                "processing_ms": round((time.perf_counter() - started) * 1000, 1),
                "timing_ms": {
                    "whole": timing_ms["whole"],
                    "surface": 0.0,
                    "verifier": timing_ms["verifier"],
                },
                "whole": selected,
                "surface_score": 0.0,
                "surface_boxes": [],
                "whole_gate": False,
                "surface_gate": False,
                "field_gate": False,
                "field_unconfirmed": False,
                "field_failed_regions": [],
                "added_marks_gate": True,
                "torn_exposed_gate": False,
                "verifier_status": "mismatch",
                "verifier_reason": v_reason,
                "label_corners": corners,
                "backend": self.backend,
            }
            return apply_guard(image, res)

        # Early-Exit 2E: Torn label exposing cardboard
        if torn_exposed_gate:
            corners = []
            if v.get("label_corners_in_crop"):
                corners = (np.array(v["label_corners_in_crop"]) + np.array(origin)).tolist()
            res = {
                "decision": "DEFECT",
                "reason": "torn label / exposed cardboard",
                "processing_ms": round((time.perf_counter() - started) * 1000, 1),
                "timing_ms": {
                    "whole": timing_ms["whole"],
                    "surface": 0.0,
                    "verifier": timing_ms["verifier"],
                },
                "whole": selected,
                "surface_score": 0.0,
                "surface_boxes": [],
                "whole_gate": False,
                "surface_gate": False,
                "field_gate": False,
                "field_unconfirmed": False,
                "field_failed_regions": [],
                "added_marks_gate": False,
                "torn_exposed_gate": True,
                "verifier_status": "mismatch",
                "verifier_reason": v_reason,
                "label_corners": corners,
                "backend": self.backend,
            }
            guarded = apply_guard(image, res)
            if guarded.get("false_torn_suppressed"):
                guarded["decision"] = "PASS"
                guarded["reason"] = "clean label; isolated border-integrity false alarm"
            return guarded

        # ---------------------------------------------------------------------
        # Step 3: Conditional Surface Model (NCNN 960x960) with Verified Logo Guard
        # Only runs for verified labels to detect physical tears/scratches on cardboard
        # ---------------------------------------------------------------------
        t_s0 = time.perf_counter()
        surf_res = self._predict(self.surface_model, image, self.surface_imgsz)
        timing_ms["surface"] = round((time.perf_counter() - t_s0) * 1000, 1)

        logo_poly = get_exact_logo_polygon(self.verifier, v, origin)

        active_boxes = []
        whole_area = 1.0
        if selected:
            x1, y1, x2, y2 = selected["xyxy"]
            whole_area = max(1.0, (x2 - x1) * (y2 - y1))

        for box in surf_res.boxes:
            sx1, sy1, sx2, sy2 = [float(val) for val in box.xyxy[0]]
            score = float(box.conf.item())
            cx, cy = (sx1 + sx2) / 2, (sy1 + sy2) / 2

            # Suppress school emblem false detections on verified labels
            inside_logo = logo_poly is not None and cv2.pointPolygonTest(logo_poly, (float(cx), float(cy)), False) >= 0
            if inside_logo:
                continue

            # Check within detected whole box
            if selected:
                ratio = (sx2 - sx1) * (sy2 - sy1) / whole_area
                if ratio <= self.surface_max_area_ratio and x1 <= cx <= x2 and y1 <= cy <= y2 and score >= self.surface_threshold:
                    active_boxes.append({"score": score, "xyxy": [sx1, sy1, sx2, sy2]})
            elif score >= self.surface_threshold:
                active_boxes.append({"score": score, "xyxy": [sx1, sy1, sx2, sy2]})

        corners = []
        if v.get("label_corners_in_crop"):
            corners = (np.array(v["label_corners_in_crop"]) + np.array(origin)).tolist()

        if active_boxes:
            top_score = max(b["score"] for b in active_boxes)
            res = {
                "decision": "DEFECT",
                "reason": "visible physical defect",
                "processing_ms": round((time.perf_counter() - started) * 1000, 1),
                "timing_ms": {
                    "whole": timing_ms["whole"],
                    "surface": timing_ms["surface"],
                    "verifier": timing_ms["verifier"],
                },
                "whole": selected,
                "surface_score": round(top_score, 4),
                "surface_boxes": active_boxes,
                "whole_gate": False,
                "surface_gate": True,
                "field_gate": False,
                "field_unconfirmed": False,
                "field_failed_regions": [],
                "added_marks_gate": False,
                "torn_exposed_gate": False,
                "verifier_status": "verified",
                "verifier_reason": v_reason,
                "label_corners": corners,
                "backend": self.backend,
            }
        else:
            res = {
                "decision": "PASS",
                "reason": "all active checks passed",
                "processing_ms": round((time.perf_counter() - started) * 1000, 1),
                "timing_ms": {
                    "whole": timing_ms["whole"],
                    "surface": timing_ms["surface"],
                    "verifier": timing_ms["verifier"],
                },
                "whole": selected,
                "surface_score": 0.0,
                "surface_boxes": [],
                "whole_gate": False,
                "surface_gate": False,
                "field_gate": False,
                "field_unconfirmed": False,
                "field_failed_regions": [],
                "added_marks_gate": False,
                "torn_exposed_gate": False,
                "verifier_status": "verified",
                "verifier_reason": v_reason,
                "label_corners": corners,
                "backend": self.backend,
            }

        return apply_guard(image, res)
