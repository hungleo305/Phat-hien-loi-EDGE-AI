#!/bin/bash
# =============================================================================
# Ví dụ lịch sử ONNX -> NCNN FP16, không phải lệnh tạo model production hiện hành.
# Để tạo ứng viên từ đúng hai checkpoint production, dùng export_ncnn.py.
# Tham chiếu Thuyết minh ĐATN: Mục 3.2.3.3
# =============================================================================

set -e

# Bước 1: Xuất mô hình PyTorch (.pt) sang định dạng ONNX
echo "[Bước 1/4] Xuất PyTorch sang ONNX..."
python -c "from ultralytics import YOLO; YOLO('best.pt').export(format='onnx', imgsz=640, opset=12, dynamic=False)"

# Bước 2: Chuyển đổi đồ thị ONNX sang định dạng NCNN (.param & .bin)
echo "[Bước 2/4] Chuyển đổi đồ thị ONNX sang NCNN..."
onnx2ncnn best.onnx model.param model.bin

# Bước 3: Tối ưu hóa đồ thị (Layer Fusion gộp Conv + BatchNorm + SiLU)
# và Lượng tử hóa bán chính xác FP16 (giảm 50% dung lượng, tận dụng ARM NEON SIMD)
echo "[Bước 3/4] Tối ưu hóa cấu trúc mạng & Lượng tử hóa FP16..."
ncnnoptimize model.param model.bin model.ncnn.param model.ncnn.bin 65536

# Bước 4: Kiểm tra tính hợp lệ và cấu hình metadata
echo "[Bước 4/4] Hoàn tất bản ví dụ NCNN FP16; chưa kiểm định để triển khai."
ls -lh model.ncnn.param model.ncnn.bin

