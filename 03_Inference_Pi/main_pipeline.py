"""
=============================================================================
ĐỒ ÁN TỐT NGHIỆP KỸ SƯ - HỌC VIỆN KỸ THUẬT MẬT MÃ
CHUYÊN NGÀNH: AN TOÀN THÔNG TIN / HỆ THỐNG NHÚNG & EDGE AI
SINH VIÊN THỰC HIỆN: CHU MẠNH HÙNG

MÃ NGUỒN: 03_Inference_Pi/main_pipeline.py
CHỨC NĂNG: ĐƯỜNG ỐNG SUY LUẬN AI ĐA TẦNG VỚI CƠ CHẾ THOÁT SỚM (EARLY-EXIT)
THAM CHIẾU BÁO CÁO: MỤC 3.2.3 & MỤC 3.2.4 - KIẾN TRÚC PHÂN LOẠI LỖI ĐA TẦNG TRÊN PI 4
=============================================================================

KIẾN TRÚC ĐƯỜNG ỐNG SUY LUẬN 3 TẦNG (3-TIER HIERARCHICAL INSPECTION):

[Khung ảnh Camera 1280x720]
          │
          ▼
┌────────────────────────────────────────────────────────────────────────┐
│ TẦNG 1 (Tier 1): PHÁT HIỆN HỘP TỔNG THỂ (YOLOv8n NCNN @ 640x640)       │
│ - Xác định vị trí vỏ hộp bìa carton (Bounding Box [x1, y1, x2, y2]).   │
│ - Nhận diện lỗi biến dạng cấu trúc nghiêm trọng (móp méo, rách lớn).   │
│ ==> THOÁT SỚM 1 (Early-Exit 1): Nếu phát hiện DEFECT cấu trúc nặng,   │
│     ra quyết định DEFECT ngay (~140ms), ngắt sớm toàn bộ quy trình.    │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ (Hộp nguyên vẹn / Nghi ngờ)
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│ TẦNG 3 (Tier 3): KIỂM ĐỊNH TEM NHÃN & TOÀN VẸN CHI TIẾT IN (ORB + NCC)  │
│ * Lưu ý: Tầng 3 được thực thi TRƯỚC Tầng 2 trong luồng chạy vì 2 lý do:│
│   1. Thoát sớm (Early-Exit): Bắt lỗi thiếu tem/sai QC/sai năm ngay mà  │
│      không cần tiêu tốn tài nguyên chạy mô hình bề mặt 960x960 nặng.   │
│   2. Tạo mặt nạ Logo Guard: Cung cấp tọa độ chính xác của logo KMA để   │
│      Tầng 2 không nhận diện nhầm nét vẽ logo thành vết nứt carton.     │
│ - Crop vùng chứa tem nhãn từ Bounding Box Tầng 1 (giảm 75% diện tích). │
│ - So khớp đặc trưng ORB + Ma trận Homography biến đổi hình học 2D.     │
│ - Kiểm tra chi tiết quan trọng: Năm kiểm định ('2026' vs '2025'),       │
│   trạng thái QC ('PASSED' vs 'FAILED'), vết bôi bẩn/rách tem.         │
│ ==> THOÁT SỚM 2 (Early-Exit 2):                                        │
│     + Thiếu tem nhãn hoàn toàn        -> DEFECT (thiếu tem)             │
│     + Sai năm hoặc QC FAILED          -> DEFECT (sai thông tin)         │
│     + Tem bị rách / vẽ đè vết mực     -> DEFECT (hư hỏng tem)          │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ (Tem hợp lệ, đạt chuẩn PASS)
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│ TẦNG 2 (Tier 2): PHÁT HIỆN LỖI BỀ MẶT VI MÔ (YOLOv8n NCNN @ 960x960)   │
│ - Chỉ kích hoạt có điều kiện khi tem đã HỢP LỆ nhằm tiết kiệm CPU Pi 4.│
│ - Quét bề mặt carton tìm lỗ thủng nhỏ, vết xước, rách mép cạnh hộp.    │
│ - Logo Suppression Guard: Sử dụng đa giác logo từ Tầng 3 để loại trừ   │
│   báo động giả do nét đồ họa của logo trường.                          │
│ ==> QUYẾT ĐỊNH CUỐI: PASS (Đạt chuẩn) hoặc DEFECT (Lỗi bề mặt carton). │
└────────────────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import time
import cv2
import numpy as np

# Kế thừa lớp cơ sở quản lý việc nạp mô hình NCNN/PyTorch và thiết lập camera
from base_pipeline import CurrentInspection as BaseInspection
# Module lọc nhiễu và triệt tiêu báo động giả do phản xạ ánh sáng/bóng đổ
from guard_logic import apply_guard


def get_exact_logo_polygon(verifier, v, origin):
    """
    Tính toán đa giác tọa độ chính xác của Logo trường Học viện Kỹ thuật Mật mã trên ảnh gốc.
    
    Thuật toán:
    1. Lấy 4 điểm góc của tem nhãn sau khi đã khớp Homography trong vùng cắt (crop).
    2. Ánh xạ ngược tọa độ chuẩn của Logo (từ template 1200x1200) sang hệ tọa độ của ảnh chụp.
    3. Đa giác này được dùng làm mặt nạ (mask) bảo vệ để Tầng 3 không báo lỗi giả lên logo.
    
    Tham số:
    - verifier: Đối tượng kiểm định tem nhãn (chứa tọa độ REGIONS['logo']).
    - v: Kết quả kiểm định tem (chứa 'label_corners_in_crop').
    - origin: Tọa độ gốc (ix1, iy1) của vùng cắt so với khung ảnh camera toàn phần.
    
    Trả về:
    - Mảng numpy float32 chứa 4 đỉnh của logo trên ảnh gốc, hoặc None nếu không tìm thấy tem.
    """
    corners = v.get("label_corners_in_crop")
    if not corners or len(corners) != 4:
        return None
    
    # 4 góc của ảnh mẫu chuẩn (canonical template coordinates)
    tpl_corners = np.float32([
        [0, 0],
        [verifier.size - 1, 0],
        [verifier.size - 1, verifier.size - 1],
        [0, verifier.size - 1]
    ])
    crop_corners = np.float32(corners)
    
    # Tính ma trận Homography chuyển từ tọa độ template sang vùng crop thực tế
    H, _ = cv2.findHomography(tpl_corners, crop_corners)
    if H is None:
        return None
        
    # Vùng chứa logo theo tỷ lệ chuẩn định nghĩa trong LabelVerifier
    lx1, ly1, lx2, ly2 = [round(val * verifier.size) for val in verifier.REGIONS['logo']]
    logo_tpl = np.float32([[[lx1, ly1]], [[lx2, ly1]], [[lx2, ly2]], [[lx1, ly2]]])
    
    # Biến đổi phối cảnh sang tọa độ vùng crop
    logo_in_crop = cv2.perspectiveTransform(logo_tpl, H).squeeze()
    # Cộng dồn offset gốc để có tọa độ trên toàn bộ khung ảnh camera
    logo_in_img = logo_in_crop + np.array(origin, dtype=np.float32)
    return logo_in_img.astype(np.float32)


class CurrentInspection(BaseInspection):
    """
    Bộ suy luận AI phân loại lỗi sản phẩm chính thức chạy trên Raspberry Pi 4 Model B.
    Thực hiện quy trình 3 tầng với cơ chế thoát sớm để đáp ứng thời gian thực (Real-time Edge AI).
    """

    def inspect(self, image):
        """
        Thực hiện kiểm định toàn diện một khung hình sản phẩm dừng trước camera.
        
        Tham số:
        - image: Khung hình BGR từ camera công nghiệp UVC (1280x720 hoặc 640x480).
        
        Trả về dictionary cấu trúc chuẩn bao gồm:
        - 'decision': 'PASS', 'DEFECT', hoặc 'REVIEW' (yêu cầu kiểm tra lại).
        - 'reason': Lý do ra quyết định kỹ thuật cụ thể.
        - 'processing_ms': Tổng thời gian xử lý toàn chu trình (ms).
        - 'timing_ms': Phân rã thời gian cho từng tầng {'whole', 'surface', 'verifier'}.
        - 'whole', 'surface_boxes', 'label_corners': Tọa độ trực quan hóa trên Dashboard.
        """
        started = time.perf_counter()
        timing_ms = {}

        # ---------------------------------------------------------------------
        # TẦNG 1: Phát hiện vỏ hộp tổng thể (Mô hình NCNN 640x640)
        # Mục tiêu: Xác định hộp carton và bắt lỗi biến dạng hình học/móp méo lớn.
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

        # Lọc các ứng viên phát hiện lỗi DEFECT vượt ngưỡng tin cậy
        defect_candidates = [
            item for item in candidates
            if item["name"] == "DEFECT" and item["score"] >= self.whole_threshold
        ]
        # Ưu tiên ứng viên DEFECT có độ tin cậy cao nhất, nếu không chọn ứng viên PASS tốt nhất
        selected = max(defect_candidates or candidates, key=lambda item: item["score"], default=None)
        whole_gate = bool(selected and selected["name"] == "DEFECT" and selected["score"] >= self.whole_threshold)

        # =====================================================================
        # THOÁT SỚM 1 (Early-Exit 1): Vỏ hộp bị móp méo / rách cấu trúc nặng
        # Không cần chạy Tầng 2 & 3 để tiết kiệm thời gian chu trình sản xuất.
        # =====================================================================
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
        # BƯỚC 2 (Thực thi Tầng 3 - LabelVerifier): Kiểm định tem nhãn (ORB + Homography)
        # Thực thi trước Tầng 2 để:
        #   1. Kích hoạt Early-Exit nếu thiếu tem / sai QC / sai năm mà không tốn tài nguyên chạy mô hình bề mặt 960x960.
        #   2. Cung cấp đa giác Logo chuẩn xác làm mặt nạ bảo vệ cho Tầng 2 (Mô hình bề mặt).
        # Cắt vùng quan tâm (ROI Crop) xung quanh hộp để giảm không gian tìm kiếm.
        # ---------------------------------------------------------------------
        t_v0 = time.perf_counter()
        crop = None
        origin = (0, 0)
        if selected is not None:
            x1, y1, x2, y2 = selected["xyxy"]
            # Mở rộng lề 30% xung quanh hộp để bao trọn mép tem nhãn
            pad = round(max(x2 - x1, y2 - y1) * 0.30)
            ix1, iy1 = max(0, round(x1) - pad), max(0, round(y1) - pad)
            ix2 = min(image.shape[1], round(x2) + pad)
            iy2 = min(image.shape[0], round(y2) + pad)
            crop = image[iy1:iy2, ix1:ix2]
            origin = (ix1, iy1)

        # Tiến hành kiểm định tem trên vùng cắt ROI
        v = self.verifier.verify(crop) if (crop is not None and crop.size) else {"status": "not_found"}
        v_reason = str(v.get("reason", ""))

        # Cơ chế dự phòng (Fallback): Nếu không tìm thấy tem trong vùng crop hoặc nghi ngờ mép cắt,
        # tự động quét lại trên toàn bộ khung ảnh gốc để tránh sót tem đặt lệch.
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

        # Đánh giá các trường thông tin sống còn (Critical Fields) và tính toàn vẹn
        fields = (v.get("integrity") or {}).get("critical_fields") or {}
        failed_critical = [r for r in v.get("failed_regions", []) if r in ("qc", "year")]
        field_gate = bool(failed_critical) or any(bool(fields.get(name, {}).get("mismatch")) for name in ("qc", "year"))
        field_unconfirmed = any(bool(fields.get(name, {}).get("insufficient")) for name in ("qc", "year"))
        added_marks_gate = "added marks on label" in v_reason
        torn_exposed_gate = "torn label / exposed cardboard" in v_reason

        # Trường hợp 2A: Không tìm thấy cả vỏ hộp lẫn tem nhãn -> REVIEW (Hàng đợi kiểm tra lại)
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

        # =====================================================================
        # THOÁT SỚM 2B (Early-Exit 2B): Có hộp nhưng THIẾU TEM HOÀN TOÀN
        # Ra quyết định DEFECT để cơ cấu gạt phân loại loại bỏ hộp lỗi ra khỏi chuyền.
        # =====================================================================
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

        # =====================================================================
        # THOÁT SỚM 2C (Early-Exit 2C): Sai trường thông tin bắt buộc (QC / Năm)
        # Ví dụ: Tem ghi năm 2025 thay vì 2026, hoặc đóng dấu QC FAILED.
        # =====================================================================
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

        # =====================================================================
        # THOÁT SỚM 2D: Phát hiện vết mực vẽ đè / bôi bẩn trên bề mặt tem
        # =====================================================================
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

        # =====================================================================
        # THOÁT SỚM 2E: Tem bị rách để lộ phần phôi giấy carton nâu bên dưới
        # =====================================================================
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
            # Áp dụng guard lọc nhiễu bóng mép tem trước khi chốt DEFECT
            guarded = apply_guard(image, res)
            if guarded.get("false_torn_suppressed"):
                guarded["decision"] = "PASS"
                guarded["reason"] = "clean label; isolated border-integrity false alarm"
            return guarded

        # ---------------------------------------------------------------------
        # BƯỚC 3 (Thực thi Tầng 2 - Surface Model): Mô hình bề mặt vi mô (NCNN 960x960)
        # Chỉ chạy có điều kiện khi tem nhãn Tầng 3 đã XÁC NHẬN HỢP LỆ (Status = verified).
        # Mục tiêu: Quét các vết rách/thủng nhỏ trên bề mặt carton ngoài vùng tem.
        # Sử dụng mặt nạ đa giác Logo từ Tầng 3 để triệt tiêu báo động giả do nét vẽ logo.
        # ---------------------------------------------------------------------
        t_s0 = time.perf_counter()
        surf_res = self._predict(self.surface_model, image, self.surface_imgsz)
        timing_ms["surface"] = round((time.perf_counter() - t_s0) * 1000, 1)

        # Xác định đa giác vùng Logo để triệt tiêu báo động giả do nét vẽ của logo
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

            # Triệt tiêu phát hiện nhầm: Nếu tâm của box nằm trong vùng Logo đã xác thực, bỏ qua!
            inside_logo = logo_poly is not None and cv2.pointPolygonTest(logo_poly, (float(cx), float(cy)), False) >= 0
            if inside_logo:
                continue

            # Kiểm tra xem box lỗi có nằm bên trong phạm vi vỏ hộp đã phát hiện không
            if selected:
                ratio = (sx2 - sx1) * (sy2 - sy1) / whole_area
                if ratio <= self.surface_max_area_ratio and x1 <= cx <= x2 and y1 <= cy <= y2 and score >= self.surface_threshold:
                    active_boxes.append({"score": score, "xyxy": [sx1, sy1, sx2, sy2]})
            elif score >= self.surface_threshold:
                active_boxes.append({"score": score, "xyxy": [sx1, sy1, sx2, sy2]})

        corners = []
        if v.get("label_corners_in_crop"):
            corners = (np.array(v["label_corners_in_crop"]) + np.array(origin)).tolist()

        # =====================================================================
        # TỔNG HỢP KẾT QUẢ CUỐI CÙNG CHO SẢN PHẨM:
        # Nếu có khuyết tật bề mặt hợp lệ -> DEFECT
        # Nếu vượt qua tất cả các tầng kiểm định -> PASS
        # =====================================================================
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

        # Áp dụng bộ lọc bảo vệ cuối cùng (Guard Logic) và trả về kết quả
        return apply_guard(image, res)
