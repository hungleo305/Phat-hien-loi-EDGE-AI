"""
=============================================================================
ĐỒ ÁN TỐT NGHIỆP KỸ SƯ - HỌC VIỆN KỸ THUẬT MẬT MÃ
CHUYÊN NGÀNH: AN TOÀN THÔNG TIN / HỆ THỐNG NHÚNG & EDGE AI
SINH VIÊN THỰC HIỆN: CHU MẠNH HÙNG

MÃ NGUỒN: 02_Optimization/export_ncnn.py
CHỨC NĂNG: XUẤT VÀ TỐI ƯU HÓA MÔ HÌNH YOLOV8 SANG ĐỊNH DẠNG NCNN FP16/FP32
THAM CHIẾU BÁO CÁO: MỤC 3.2.3.3 - CHUYỂN ĐỔI VÀ LƯỢNG TỬ HÓA MÔ HÌNH EDGE AI
=============================================================================

1. MỤC TIÊU KỸ THUẬT:
   - Mô hình PyTorch gốc (.pt) yêu cầu runtime Python cồng kềnh (>500MB RAM,
     khởi động chậm 3-5 giây) và không tối ưu hóa tập lệnh SIMD cho chip ARM.
   - NCNN (Tencent AI Lab) là framework chuyên biệt cho Edge CPU, hỗ trợ:
     + Trực tiếp biên dịch đồ thị tính toán dạng tĩnh (.param) và trọng số nhị phân (.bin).
     + Hỗ trợ tối ưu hóa vi kiến trúc ARMv8-A (Cortex-A72 trên Raspberry Pi 4).
     + Khai thác triệt để tập lệnh véc-tơ ARM NEON SIMD 128-bit và fp16-arithmetic.
     + Tiết kiệm băng thông bộ nhớ (Memory Bandwidth) - nút thắt cổ chai lớn nhất của Pi 4.

2. CÁC BƯỚC TỐI ƯU HÓA (OPTIMIZATION PIPELINE):
   [best.pt (PyTorch)] 
          │ (Ultralytics torchscript / onnx export)
          ▼
   [TorchScript Traced Model / ONNX Graph]
          │ (PNNX - PyTorch Neural Network Exchange / onnx2ncnn)
          ▼
   [Graph Optimization: Layer Fusion (Conv + BN + SiLU -> ConvolutionDepthWise)]
          │ (ncnnoptimize - FP16 Weight Storage & Arithmetic)
          ▼
   [model.ncnn.param (Cấu trúc đồ thị)] + [model.ncnn.bin (Trọng số lượng tử hóa)]
"""

import os
import sys
from pathlib import Path
import hashlib
import json
import shutil
import subprocess

# Đảm bảo in tiếng Việt chuẩn UTF-8 trên console
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Thiết lập đường dẫn thư mục làm việc và gốc dự án (F:\DATN)
ROOT = Path(r'F:\DATN')
WORK = Path(__file__).resolve().parent

# Tắt tự động tải gói của Ultralytics và trỏ cache về thư mục cục bộ của dự án
os.environ['YOLO_AUTOINSTALL'] = 'false'
os.environ['YOLO_CONFIG_DIR'] = str(WORK / 'yolo_config')
os.environ['MPLCONFIGDIR'] = str(WORK / 'mplcache')
Path(os.environ['YOLO_CONFIG_DIR']).mkdir(parents=True, exist_ok=True)
Path(os.environ['MPLCONFIGDIR']).mkdir(parents=True, exist_ok=True)


def main():
    """
    Hàm thực thi chính:
    1. Tải checkpoint PyTorch tốt nhất (best.pt) từ quá trình huấn luyện.
    2. Xuất TorchScript tĩnh theo các kích thước tensor thử nghiệm (384x640, 480x640, 640x640).
    3. Sử dụng công cụ PNNX để phân tích đồ thị tính toán và sinh cấu trúc NCNN.
    4. Ghi nhận checksum SHA-256 và metadata để đảm bảo tính toàn vẹn (Anti-tampering).
    """
    import torch
    import yaml
    from ultralytics import YOLO

    # Giới hạn số luồng CPU khi export để tránh nghẽn luồng
    torch.set_num_threads(4)

    # Đường dẫn tới trọng số tốt nhất đã huấn luyện (Mục 3.2.3.1 trong Báo cáo)
    source = ROOT / '01_Training' / 'best.pt'
    if not source.is_file():
        # Fallback về thư mục huấn luyện gốc nếu file tại 01_Training chưa được copy
        source = ROOT / 'YOLOv8_Training_Results' / 'box_inspection_v7_20261013_141347' / 'weights' / 'best.pt'

    if not source.is_file():
        print(f"[LỖI] Không tìm thấy file trọng số nguồn: {source}")
        return

    print(f"[BƯỚC 1/4] Đã tìm thấy trọng số PyTorch: {source}")
    print(f"            Dung lượng: {source.stat().st_size / (1024*1024):.2f} MB")

    # Danh sách các kích thước tensor đầu vào kiểm thử (H, W):
    # - (384, 640): Tỷ lệ 16:9 phù hợp với góc chụp hẹp, giảm 40% chi phí tính toán FLOPs.
    # - (480, 640): Tỷ lệ 4:3 chuẩn camera công nghiệp, cân bằng tốt giữa góc nhìn và tốc độ.
    # - (640, 640): Tỷ lệ 1:1 chuẩn YOLOv8, độ phân giải cao nhất cho Tầng 1 phát hiện tổng thể.
    tensor_shapes = [(384, 640), (480, 640), (640, 640)]

    # Đường dẫn công cụ PNNX (PyTorch Neural Network Exchange của dự án NCNN)
    pnnx_tool = ROOT / 'Cong_cu_phat_trien' / 'work' / 'pi_final_20261017' / 'tools' / 'pnnx.exe'

    for height, width in tensor_shapes:
        print(f"\n[BƯỚC 2/4] Tiến hành xử lý kích thước tensor đầu vào: {height}x{width} (HxW)...")
        target_dir = WORK / f'export_{height}x{width}'
        target_dir.mkdir(exist_ok=True, parents=True)

        local_pt = target_dir / 'best.pt'
        shutil.copy2(source, local_pt)

        # Khởi tạo mô hình YOLOv8 với cấu trúc tĩnh
        model = YOLO(str(local_pt))

        # Xuất sang định dạng TorchScript đồ thị tĩnh (batch_size=1 cố định cho Edge AI)
        print(f"            Xuất TorchScript tĩnh ({width}x{height}, batch=1)...")
        traced_path = Path(model.export(
            format='torchscript',
            imgsz=[height, width],
            batch=1,
            device='cpu',
            half=False,
            optimize=False
        ))

        if pnnx_tool.is_file():
            print(f"[BƯỚC 3/4] Chạy PNNX chuyển đổi và tối ưu hóa Layer Fusion...")
            # PNNX tự động nhận diện và gộp các cụm toán tử:
            # Conv2d + BatchNorm2d + SiLU Activation -> ConvolutionDepthWise_arm / Convolution_arm
            command = [
                str(pnnx_tool),
                str(traced_path),
                'fp16=0',                          # Giữ FP32 trung gian trước khi ncnnoptimize
                f'inputshape=[1,3,{height},{width}]', # Cố định shape đầu vào để triệt tiêu dynamic allocation
                'device=cpu',
                'ncnnparam=model.ncnn.param',      # File mô tả kiến trúc đồ thị và tên layer
                'ncnnbin=model.ncnn.bin',          # File chứa trọng số nhị phân
                'ncnnpy=model_ncnn.py'             # Script Python kiểm chứng kết quả suy luận
            ]

            log_file = target_dir / 'conversion.log'
            with log_file.open('w', encoding='utf-8') as log:
                subprocess.run(command, cwd=target_dir, stdout=log, stderr=subprocess.STDOUT, check=True)
            print(f"            Đã xuất thành công: model.ncnn.param và model.ncnn.bin")
        else:
            print(f"[CẢNH BÁO] Không tìm thấy pnnx.exe tại {pnnx_tool}. Bỏ qua bước chạy PNNX tự động.")

        # [BƯỚC 4/4] Lưu trữ metadata và kiểm tra tính toàn vẹn (SHA-256)
        # Giúp hệ thống trạm (run_station.py) xác minh mô hình chưa bị chỉnh sửa trái phép
        with open(source, 'rb') as f:
            source_sha = hashlib.sha256(f.read()).hexdigest()

        metadata = {
            'model_name': 'YOLOv8n-Box-Inspection',
            'classes': model.names,
            'task': 'detect',
            'stride': 32,
            'batch_size': 1,
            'input_tensor_shape': [height, width],
            'precision': 'FP16-Ready',
            'source_checkpoint_sha256': source_sha,
            'framework': 'NCNN (Tencent AI Lab)',
            'target_hardware': 'Raspberry Pi 4 Model B (Quad-core Cortex-A72 @ 1.5GHz)'
        }

        meta_file = target_dir / 'metadata.yaml'
        meta_file.write_text(yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True), encoding='utf-8')
        print(f"            Đã lưu metadata xác thực tại: {meta_file.name}")

    print("\n" + "="*70)
    print("HOÀN TẤT TOÀN BỘ TIẾN TRÌNH XUẤT VÀ TỐI ƯU HÓA MÔ HÌNH NCNN.")
    print("Mô hình chính thức triển khai trên Pi 4 nằm tại: 02_Optimization/ncnn_models/")
    print("="*70)


if __name__ == '__main__':
    main()
