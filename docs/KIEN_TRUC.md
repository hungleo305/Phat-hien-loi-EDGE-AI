# Cấu trúc mã và phụ thuộc

Luồng điều khiển: cảm biến → ESP32/FIFO → UART CAPTURE → station → camera → runtime AI → UART RESULT → ESP32/servo. Dashboard gọi station để gửi lệnh và đọc trạng thái; JavaScript không trực tiếp điều khiển GPIO.

## Nguồn duy nhất cho từng thành phần

- `03_Inference_Pi/runtime`: toàn bộ AI, model, mẫu tem và cấu hình. Không import bản sao thuật toán ở module khác.
- `03_Inference_Pi/camera_profile.json`: cấu hình UVC/V4L2 của Pi; không quy trực tiếp sang exposure camera Windows.
- `05_Dashboard/station`: điều phối trạm và toàn bộ web assets. Laptop gateway cũng đọc assets từ đây.
- `04_ESP32_Firmware`: mã firmware dùng chung cho laptop và Git.
- `01_Training`, `02_Optimization`: công cụ tạo kết quả mới, không chạy trong vòng điều khiển production.
- `docs/evidence`: dữ liệu minh chứng đã chọn, có README mô tả điều kiện và SHA256SUMS.

## Dữ liệu ngoài Git

Laptop giữ ảnh gốc và dữ liệu huấn luyện trong `F:/DATN/Du_lieu_goc`; kết quả camera, số đo và build trong `F:/DATN/Cong_cu_phat_trien/outputs`. Khóa SSH ở gateway laptop không được commit. Pi giữ môi trường `.venv`, `.secrets`, camera captures và lịch sử bên ngoài mã Git.

## Manifest và triển khai

Runtime và station có `manifest.json` ghi SHA-256 các tệp trong gói. Thay một tệp được quản lý đòi hỏi rà soát và cập nhật hash có chủ đích; không sửa manifest chỉ để bỏ qua lỗi kiểm tra. Gói Git có README mới nên hash README khác snapshot lịch sử; model/config/thuật toán giữ nguyên.

Push Git chỉ cập nhật kho nguồn. Khi triển khai, phải kiểm hash, self-check, API, camera/UART và thử phần cứng phù hợp trước khi chốt bản chạy. Không lấy lại ứng viên FP16 hoặc surface 832/768 vì chỉ có tệp nhỏ hơn.
