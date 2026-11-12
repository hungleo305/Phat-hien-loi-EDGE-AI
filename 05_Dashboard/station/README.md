# Gói điều phối trạm và giao diện Web (`05_Dashboard/station`)

Thư mục này chứa mã nguồn chuẩn đang chạy trên Raspberry Pi 4 (`/home/cmh/Pi4_EdgeAI/current/station`) để phối hợp giữa Camera USB, gói suy luận [`03_Inference_Pi/runtime`](../../03_Inference_Pi/runtime/README.md), cổng giao tiếp UART2 tới ESP32 và máy chủ Web Dashboard.

---

## 1. Thành phần trong gói `station/`

| Tên tệp | Vai trò |
|---|---|
| [`run_station.py`](run_station.py) | Tiến trình điều phối chính: nhận bản tin `CAPTURE` từ ESP32, chụp ảnh camera, trả lời `CAPTURED`, gọi hàm kiểm định AI và gửi `RESULT` (`PASS`, `DEFECT`, hoặc chuyển `REVIEW -> ERROR`). |
| [`station_protocol.py`](station_protocol.py) | Quản lý phiên giao tiếp UART2, đối chiếu mã phiên (`session`), số thứ tự (`seq`), mã hộp (`id`) và phản hồi `OPACK`. |
| [`dashboard.py`](dashboard.py) | Máy chủ HTTP nội bộ phục vụ giao diện web, luồng MJPEG, quản lý phiên kiểm định và xuất dữ liệu CSV/JSON. |
| [`dashboard.html`](dashboard.html), [`dashboard.css`](dashboard.css), [`dashboard.js`](dashboard.js) | Bộ tệp giao diện trình duyệt duy nhất của hệ thống. |
| [`startup_defaults.py`](startup_defaults.py), [`station_defaults.json`](station_defaults.json) | Áp dụng bộ thông số mặc định (`SPEED=180`, `LIGHT=70`, `SERVO_ANGLE=60`, `SERVO_HOLD=350`) khi trạm ở trạng thái `STOPPED` và cảm biến trống. |
| [`manifest.json`](manifest.json) | Danh sách mã băm SHA-256 của toàn bộ 9 tệp trong gói `station/`. |

---

## 2. Khởi chạy và kiểm tra

Khi chạy từ gốc kho mã nguồn, sử dụng kịch bản [`03_Inference_Pi/run_station.py`](../../03_Inference_Pi/run_station.py) để tự động nạp đúng gói `runtime/` và `camera_profile.json`. Xem hướng dẫn chi tiết tại [`../README.md`](../README.md) và [`../../docs/VAN_HANH.md`](../../docs/VAN_HANH.md).
