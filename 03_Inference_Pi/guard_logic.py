"""Fixed-camera guards tuned for recorded physical-box inventory and scalable live cameras."""
from __future__ import annotations

import cv2
import numpy as np


def blank_label_signal(image) -> tuple[bool, float, float]:
    h, w = image.shape[:2]
    if (h, w) == (720, 1280):
        roi = image[130:600, 350:930]
    else:
        y1, y2 = round(130 * h / 720), round(600 * h / 720)
        x1, x2 = round(350 * w / 1280), round(930 * w / 1280)
        roi = image[y1:y2, x1:x2]
    if roi.size == 0:
        return False, -1.0, -1.0
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    bright_fraction = float((gray > 85).mean())
    edge_fraction = float((cv2.Canny(gray, 70, 140) > 0).mean())
    return bright_fraction >= .20 and edge_fraction < .025, bright_fraction, edge_fraction


def silhouette_concavity(image) -> float:
    h, w = image.shape[:2]
    if (h, w) == (720, 1280):
        roi = image[100:620, 300:950]
        min_hull = 15000
    else:
        y1, y2 = round(100 * h / 720), round(620 * h / 720)
        x1, x2 = round(300 * w / 1280), round(950 * w / 1280)
        roi = image[y1:y2, x1:x2]
        min_hull = round(15000 * (h * w) / (720 * 1280))
    if roi.size == 0:
        return -1.0
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    mask = cv2.morphologyEx((gray > 85).astype(np.uint8) * 255,
                            cv2.MORPH_CLOSE, np.ones((7, 7), dtype=np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return -1.0
    contour = max(contours, key=cv2.contourArea)
    hull_area = cv2.contourArea(cv2.convexHull(contour))
    if hull_area < min_hull:
        return -1.0
    return 1 - cv2.contourArea(contour) / hull_area


def apply_guard(image, result):
    blank, bright_fraction, edge_fraction = blank_label_signal(image)
    concavity = silhouette_concavity(image)
    result["blank_guard_bright_fraction"] = round(bright_fraction, 5)
    result["blank_guard_edge_fraction"] = round(edge_fraction, 5)
    result["silhouette_concavity"] = round(concavity, 5)
    result["blank_guard_gate"] = False
    result["deformation_guard_gate"] = False
    result["false_torn_suppressed"] = False
    if blank and result.get("whole") and result["verifier_status"] == "not_found":
        result["decision"] = "DEFECT"
        result["reason"] = "missing label on detected cardboard box"
        result["blank_guard_gate"] = True
    elif (result["decision"] in ("PASS", "REVIEW") and concavity >= .025
          and result.get("whole") and
          (result["verifier_reason"] == "label content differs in logo, school"
           or (result["whole"]["name"] == "DEFECT" and result["whole"]["score"] >= .60))):
        result["decision"] = "DEFECT"
        result["reason"] = "deformed box/label silhouette"
        result["deformation_guard_gate"] = True
    elif (result["decision"] in ("PASS", "REVIEW", "DEFECT") and result["torn_exposed_gate"]
          and result.get("whole") and result["whole"]["name"] == "PASS"
          and result["surface_score"] == 0 and not result["field_gate"]
          and not result["field_unconfirmed"] and concavity >= 0
          and concavity < .020 and edge_fraction >= .040):
        result["decision"] = "PASS"
        result["reason"] = "clean label; isolated border-integrity false alarm"
        result["false_torn_suppressed"] = True
    return result
