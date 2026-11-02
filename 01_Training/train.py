"""
================================================================================
DỰ ÁN ĐỒ ÁN TỐT NGHIỆP: THIẾT KẾ HỆ THỐNG EDGE AI PHÁT HIỆN LỖI SẢN PHẨM
Học viên: Chu Mạnh Hùng - Học viện Kỹ thuật Mật mã (KMA)
Mã nguồn: 01_Training/train.py - Huấn luyện mô hình Tầng 1 (Toàn hộp)
Tham chiếu thuyết minh: Mục 3.2.3.1 & Mục 3.2.3.2
================================================================================
Vai trò tệp:
- Tinh chỉnh (fine-tune) mô hình YOLOv8n (Nano) để nhận diện vùng toàn hộp và
  phân loại nhị phân sơ bộ giữa sản phẩm đạt chuẩn (PASS) và lỗi (DEFECT).
- Khắc phục hiện tượng mất cân bằng mẫu bằng cách tăng cường dữ liệu và thiết
  lập tỷ lệ 150 PASS / 155 DEFECT trong tập Train.
================================================================================
"""

import json
from pathlib import Path
import torch
from ultralytics import YOLO

# -----------------------------------------------------------------------------
# 1. Cấu hình đường dẫn thư mục và dữ liệu
# -----------------------------------------------------------------------------
ROOT = Path(r"F:\DATN")
BASE = Path(__file__).resolve().parent

# File cấu hình tập dữ liệu (khai báo train/val/test và nhãn lớp)
DATA_YAML = BASE / "data.yaml"

# Trọng số tiền huấn luyện (v2 checkpoint) làm điểm xuất phát tối ưu
PRETRAIN_WEIGHTS = ROOT / "Cong_cu_phat_trien/outputs/newlabel_v2_20261028/training/v2_yolov8n_rotation_640/weights/best.pt"

# Thư mục lưu kết quả huấn luyện
PROJECT_DIR = ROOT / "Cong_cu_phat_trien/outputs/newlabel_v4_20261028/training"
RUN_NAME = "whole_balanced_finetune_640"
RUN_DIR = PROJECT_DIR / RUN_NAME

# Kiểm tra điều kiện tiên quyết: Card đồ họa NVIDIA CUDA và tệp checkpoint gốc
if not torch.cuda.is_available():
    print("[CẢNH BÁO] Không tìm thấy GPU CUDA. Huấn luyện sẽ chạy trên CPU (chậm hơn).")
    DEVICE = "cpu"
else:
    DEVICE = 0

if not DATA_YAML.is_file():
    raise FileNotFoundError(f"Không tìm thấy tệp cấu hình dữ liệu: {DATA_YAML}")

# -----------------------------------------------------------------------------
# 2. Thiết lập siêu tham số huấn luyện (Hyperparameters)
# -----------------------------------------------------------------------------
# - Kiến trúc mạng: YOLOv8n (3.2 triệu tham số, nhẹ nhất trong họ YOLOv8).
# - Kích thước ảnh đầu vào (imgsz): 640x640 pixel (chuẩn tối ưu tốc độ/độ chính xác).
# - Kích thước batch (batch): 4 (phù hợp với dung lượng VRAM GPU máy tính xách tay).
# - Thuật toán tối ưu hóa (optimizer): AdamW (hội tụ nhanh, tránh phân kỳ trọng số).
# - Tốc độ học ban đầu (lr0): 0.001, hệ số suy giảm cosine (lrf): 0.01.
# - Số epoch tối đa (epochs): 25, dừng sớm (patience): 8 epoch không cải thiện.
#
# Chiến lược tăng cường dữ liệu (Data Augmentation) phù hợp với cơ cấu Stop & Go:
# - degrees=180: Hộp trên băng tải có thể xoay góc nghiêng ngẫu nhiên khi di chuyển.
# - translate=0.04, scale=0.10: Biến thiên nhẹ vị trí và khoảng cách camera.
# - fliplr=0, flipud=0: TUYỆT ĐỐI KHÔNG lật gương ảnh vì tem in chứa ký tự chữ/số.
# - mosaic=0, mixup=0: TẮT ghép ảnh để giữ nguyên bối cảnh vật lý thật của băng chuyền.
# - hsv_s=0.05, hsv_v=0.12: Mô phỏng dao động độ rọi đèn LED (dao động độ sáng).
# -----------------------------------------------------------------------------

def main():
    print(f"[*] Bắt đầu huấn luyện mô hình Tầng 1: {RUN_NAME}")
    
    # Nạp mô hình gốc YOLOv8n
    model_source = str(PRETRAIN_WEIGHTS) if PRETRAIN_WEIGHTS.is_file() else "yolov8n.pt"
    model = YOLO(model_source)

    # Thực thi quá trình huấn luyện
    model.train(
        data=str(DATA_YAML),
        epochs=25,
        patience=8,
        imgsz=640,
        batch=4,
        device=DEVICE,
        workers=0,              # workers=0 tránh lỗi đa tiến trình bộ nhớ trên Windows
        seed=24,                # Khóa seed để kết quả thực nghiệm có thể tái lập
        deterministic=True,
        project=str(PROJECT_DIR),
        name=RUN_NAME,
        exist_ok=True,
        plots=True,             # Tự động vẽ biểu đồ PR-curve, F1-curve, confusion matrix
        optimizer="AdamW",
        lr0=0.001,
        lrf=0.01,
        degrees=180,            # Hỗ trợ xoay hộp góc bất kỳ trên băng chuyền
        translate=0.04,
        scale=0.10,
        shear=0,
        perspective=0,
        flipud=0,               # Không lật dọc
        fliplr=0,               # Không lật ngang (bảo toàn hướng tem)
        mosaic=0,               # Tắt ghép 4 ảnh ảo
        mixup=0,
        copy_paste=0,
        hsv_h=0,
        hsv_s=0.05,
        hsv_v=0.12              # Chống chịu dao động ánh sáng
    )

    # -------------------------------------------------------------------------
    # 3. Đánh giá kiểm định độc lập trên tập Test
    # -------------------------------------------------------------------------
    best_weights = RUN_DIR / "weights/best.pt"
    if not best_weights.is_file():
        raise FileNotFoundError(f"Không tìm thấy tệp trọng số xuất xưởng: {best_weights}")

    print(f"[✓] Huấn luyện hoàn tất. Tệp trọng số tối ưu: {best_weights}")
    print("[*] Đang đánh giá kiểm thử trên tập Test độc lập...")

    best_model = YOLO(str(best_weights))
    test_metrics = best_model.val(
        data=str(DATA_YAML),
        split="test",
        imgsz=640,
        batch=4,
        device=DEVICE,
        workers=0,
        plots=True,
        project=str(RUN_DIR),
        name="test_evaluation",
        exist_ok=True,
    )

    # Lưu bản tổng hợp chỉ số kỹ thuật (mAP50, Precision, Recall)
    summary_data = {
        "model_path": str(best_weights),
        "dataset_config": str(DATA_YAML),
        "imgsz": 640,
        "batch": 4,
        "metrics_test": {k: float(v) for k, v in test_metrics.results_dict.items()},
    }
    
    summary_path = RUN_DIR / "metrics_summary.json"
    summary_path.write_text(json.dumps(summary_data, indent=2), encoding="utf-8")
    print(f"[✓] Đã xuất bản tổng hợp số đo kiểm thử: {summary_path}")


if __name__ == "__main__":
    main()
