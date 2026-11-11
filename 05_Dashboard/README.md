# Dashboard
Máy chủ HTTP và giao diện của trạm Pi. server.py cung cấp lớp Dashboard, không phải lệnh khởi động độc lập. Trạm production khởi động qua service trên Pi.
Giao diện cập nhật trạng thái mỗi 1500 ms. DRY là chạy thử không gạt; SORT cho phép gạt DEFECT. Độ trễ hiển thị là CAPTURE-to-RESULT, không bao gồm thời gian trình duyệt hiển thị.

## Cập nhật vận hành 11/11/2026

- Tạo phiên mới đặt số hộp và PASS/DEFECT/ERROR về 0. Kết quả đầu tiên trong phiên hiển thị #1; chọn phiên cũ để xem thống kê riêng. CSV có `stt_trong_phien`, giữ mã ESP32 gốc để truy vết.
- Khi tạo phiên, ảnh cũ được xóa ngay. Phản hồi tải ảnh của phiên trước đến trễ không được hiển thị lại. CSS tôn trọng thuộc tính `hidden` và giữ thông báo trống ở giữa khung.
- Nhãn cài đặt dùng chữ thường; hộp cài đặt bỏ bóng đổ lớn.
- `station/station_defaults.json`: PWM 180, LED 70, góc gạt 60°, chờ thu tay 350 ms. `startup_defaults.py` áp dụng một lần khi trạm khởi động hoặc ESP32 đổi session, chỉ khi STOPPED, cảm biến trống và trạm rảnh; chờ ACK và kiểm tra STATE. Không tự START motor, không ghi đè chỉnh tay sau khi khởi tạo xong.
- Phơi sáng camera đã lưu 1100 trong `../03_Inference_Pi/camera_profile.json`. Các thông số ESP32 trên được Pi áp dụng; không phải thay mặc định trong firmware khi ESP32 chạy riêng.

`station/` là bản điều phối đồng bộ từ Pi; manifest kiểm tra nguyên vẹn các file. `server.py` là bản sao thư viện `station/dashboard.py`. Các cặp `index.html`/`dashboard.html` và `app.js`/`dashboard.js` ở gốc được đồng bộ cho các điểm mở giao diện khác nhau.

## Shortcut trên desktop Pi

`pi_desktop/` chứa script và launcher đang dùng. Với bản production ở `/home/cmh/Pi4_EdgeAI`, chép `open_dashboard.sh` vào thư mục đó và `datn-dashboard.desktop` vào `~/Desktop/`, cấp quyền chạy cho cả hai. Launcher dùng dịch vụ user `datn-station.service`, đợi API rồi mở Chromium tại `http://127.0.0.1:8768`; không khởi động băng tải. Các đường dẫn này dành cho máy Pi hiện tại, cần điều chỉnh nếu cài sang tài khoản khác.

## Kiểm tra

Chạy từ gốc kho:

```bash
python 05_Dashboard/tests/check_runs.py
python 05_Dashboard/tests/check_defaults.py
node 05_Dashboard/tests/check_image.cjs
node --check 05_Dashboard/dashboard.js
```

Các kiểm tra dùng dữ liệu tạm riêng; không tạo phiên trong dữ liệu production. Kiểm thử khôi phục thực tế trên Pi đã xác nhận PWM 179 về 180 sau restart dịch vụ và camera nạp lại 1100; chưa thử power-cycle toàn hệ thống. Thuật toán AI, model và ngưỡng phân loại không đổi trong cập nhật này.
