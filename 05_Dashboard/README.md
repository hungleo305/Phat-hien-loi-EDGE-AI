# Trạm điều phối và dashboard

Mã chạy duy nhất nằm trong `station/`. Trạm nhận CAPTURE từ ESP32, lấy ảnh, gọi runtime AI, gửi RESULT và cung cấp web dashboard. Không còn các bản HTML/JS/server sao chép tại gốc module.

| Tệp trong station | Vai trò |
|---|---|
| `run_station.py` | Điều phối camera, tiến trình AI, UART và dashboard |
| `station_protocol.py` | Đọc bản tin và giao dịch theo phiên/ID |
| `dashboard.py` | HTTP API, MJPEG, lịch sử và xuất CSV/JSON |
| `dashboard.html`, `dashboard.css`, `dashboard.js` | Giao diện trình duyệt |
| `startup_defaults.py`, `station_defaults.json` | Áp dụng mặc định khi dừng/trống, chờ ACK và STATE |
| `manifest.json` | Kiểm tra các tệp đồng bộ trong gói station |

## Vận hành

Dùng `../03_Inference_Pi/run_station.py` để nạp đúng runtime và profile. Trên Pi hiện tại, dịch vụ đã quản lý trạm; mở dashboard tại `http://127.0.0.1:8768` hoặc dùng launcher trong `pi_desktop/`. Laptop dùng gateway riêng tại cổng 8769. Mở trình duyệt không gửi START motor.

Tạo phiên trước khi chạy. Bộ đếm và số thứ tự hộp thuộc phiên đang xem; ID ESP32 gốc vẫn giữ để truy vết. Khi tạo phiên mới, ảnh kết quả cũ được xóa khỏi vùng hiển thị; dữ liệu phiên trước vẫn có trong lịch sử.

Mặc định Pi: LED 70, PWM 180, góc gạt 60°, chờ thu 350 ms; chỉ áp dụng lúc STOPPED, cảm biến trống và trạm rảnh. Không ghi đè chỉnh tay liên tục. Camera profile ở `../03_Inference_Pi/camera_profile.json`, phơi sáng đã lưu 1100. Góc/thời gian là giá trị ra lệnh, chưa có phản hồi vị trí servo.

## Kiểm tra từ gốc kho

```bash
python 05_Dashboard/tests/check_runs.py
python 05_Dashboard/tests/check_defaults.py
node 05_Dashboard/tests/check_image.cjs
node --check 05_Dashboard/station/dashboard.js
```

Các kiểm tra dùng dữ liệu tạm, không tạo phiên trên production. Không đo năng suất cơ khí hoặc chứng minh điều khiển an toàn trong mọi tình huống. [Hướng dẫn vận hành](../docs/VAN_HANH.md) và [ảnh/số liệu dashboard](../docs/evidence/dashboard/README.md) cung cấp ngữ cảnh.

## Launcher desktop Pi

`pi_desktop/open_dashboard.sh` đặt tại `/home/cmh/Pi4_EdgeAI`; `datn-dashboard.desktop` đặt tại `~/Desktop`, cấp quyền chạy. Đây là cấu hình cho tài khoản `cmh`; cần điều chỉnh nếu đổi máy. Launcher đợi API của dịch vụ rồi mở Chromium, không tự START băng tải.
