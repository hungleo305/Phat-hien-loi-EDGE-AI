# Hệ thống kiểm định hộp Edge AI

## Các mô-đun
- 01_Training: huấn luyện và đánh giá YOLO.
- 02_Optimization: xuất ứng viên NCNN FP16 riêng; production vẫn FP32.
- 03_Inference_Pi/runtime: bản runtime đồng bộ từ Pi, có config, model và manifest.
- 04_ESP32_Firmware: firmware một task điều khiển, UART2, FIFO và servo.
- 05_Dashboard: giao diện và thư viện máy chủ dashboard.

Pipeline: toàn hộp NCNN 640 → kiểm định tem ORB/Homography/NCC → bề mặt NCNN 960 khi cần. REVIEW không tự thành PASS.

Kiểm tra AI: `python 03_Inference_Pi/runtime/self_check.py --backend ncnn`.
Các tệp Python ở gốc 03_Inference_Pi là bản trình bày mã; đường kiểm thử chuẩn là runtime.
Đây là kho mã nguồn, không phải thao tác triển khai lên Pi.

Ngày 11/11/2026: đồng bộ dashboard theo phiên, xử lý xóa ảnh khi tạo phiên, cấu hình mặc định vận hành và shortcut desktop Pi. Xem `05_Dashboard/README.md`. Camera lưu phơi sáng 1100; Pi áp dụng PWM 180, LED 70, góc gạt 60°, chờ thu 350 ms khi đủ điều kiện dừng/trống.

ESP32 chạy lại sau CAPTURED hợp lệ, lưu RESULT theo phiên/ID vào FIFO; chỉ dừng chờ tại cửa gạt nếu chưa có kết quả. Đã quan sát gạt đúng hộp trong điều kiện chạy thử được xác nhận; chưa có đánh giá vận hành dài hạn.

## Đối chứng xử lý ảnh
Cùng 11 ảnh, lặp ba lượt, NCNN CPU: Pi trung bình 0,984 s/ảnh, Acer i5-11400H trung bình 0,158 s/ảnh; quyết định khớp trên bộ thử. Pi 4 luồng, Acer 6 luồng. Đây là thời gian kiểm định ảnh, chưa gồm camera/UART/cơ cấu gạt; bộ nhỏ không chứng minh độ chính xác chung.
Lưu đồ chức năng nằm trong docs/diagrams.

## Hồ sơ thực nghiệm cho báo cáo

Các bảng số liệu, dữ liệu từng ảnh/lượt và ảnh dashboard được công bố tại [docs/evidence](docs/evidence/). Mỗi nhóm giải thích đơn vị, phương pháp và giới hạn của kết quả để người đọc đối chiếu các số liệu trong báo cáo.
