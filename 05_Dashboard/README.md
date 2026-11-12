# Phân hệ 05 — Phần mềm điều phối trạm và Web Dashboard

Thư mục này chứa phần mềm điều phối trung tâm trên Raspberry Pi 4 (**`station/`**), kết nối giữa Camera USB, tiến trình suy luận AI (`03_Inference_Pi/runtime`), cổng truyền thông UART2 tới ESP32 và giao diện điều khiển **Web Dashboard**.

---

## 1. Cấu trúc phân hệ

| Thành phần | Vai trò |
|---|---|
| [`station/run_station.py`](station/run_station.py) | Chương trình điều phối chính của trạm: quản lý luồng đọc camera, gọi hàm kiểm định AI, gửi/nhận bản tin UART2 và duy trì nhịp `HEARTBEAT`. |
| [`station/station_protocol.py`](station/station_protocol.py) | Xử lý giao thức truyền thông nối tiếp với ESP32 theo phiên (`session`), số thứ tự lệnh (`seq`), mã hộp (`id`) và xác nhận `OPACK`. |
| [`station/dashboard.py`](station/dashboard.py) | Máy chủ HTTP nội bộ cung cấp REST API (`/api/state`, `/api/command`, `/api/runs`...), luồng video trực tiếp **MJPEG** và xuất báo cáo **CSV / JSON**. |
| [`station/dashboard.html`](station/dashboard.html), [`dashboard.css`](station/dashboard.css), [`dashboard.js`](station/dashboard.js) | Giao diện người dùng trên trình duyệt web: hiển thị trạng thái thiết bị, video trực tiếp, ảnh kết quả kiểm định, bộ đếm theo phiên và bảng lịch sử. |
| [`station/startup_defaults.py`](station/startup_defaults.py), [`station_defaults.json`](station/station_defaults.json) | Cơ chế tự động áp dụng thông số chuẩn (`SPEED=180`, `LIGHT=70`, `SERVO_ANGLE=60`, `SERVO_HOLD=350`) khi trạm ở trạng thái dừng và cảm biến trống. |
| [`station/manifest.json`](station/manifest.json) | Danh mục mã băm SHA-256 bảo vệ tính toàn vẹn của toàn bộ 9 tệp trong gói `station/`. |
| [`pi_desktop/`](pi_desktop/) | Kịch bản `open_dashboard.sh` và biểu tượng `datn-dashboard.desktop` ngoài màn hình Raspberry Pi 4. |
| [`tests/`](tests/) | Bộ kiểm thử tự động cho quản lý phiên chạy (`check_runs.py`), đồng bộ thông số mặc định (`check_defaults.py`) và hiển thị ảnh giao diện (`check_image.cjs`). |

---

## 2. Các tính năng chính của Web Dashboard

1. **Giám sát trực quan theo thời gian thực**:
   - Hiển thị luồng hình ảnh trực tiếp từ camera buồng chụp (MJPEG) song song với ảnh kết quả kiểm định mới nhất (đã vẽ khung bao hộp, khung tem và nhãn quyết định `PASS` / `DEFECT`).
   - Hiển thị trạng thái kết nối của Pi, Camera, AI, ESP32, trạng thái hai cảm biến và số hộp đang nằm trong hàng đợi FIFO.
2. **Quản lý theo từng phiên kiểm định (`Run Session`)**:
   - Khi tạo phiên mới, bộ đếm (`Tổng`, `PASS`, `DEFECT`, `ERROR`) được đặt lại về `0` và số thứ tự hộp hiển thị bắt đầu từ `#1` trong phiên, đồng thời vẫn lưu mã `ID` gốc của ESP32 để đối chiếu nhật ký phần cứng.
   - Cho phép xem lại lịch sử các phiên trước và tải xuống toàn bộ bản ghi thời gian (`capture_ms`, `ai_ms`, `request_to_result_ms`) dưới dạng tệp **CSV** hoặc **JSON**.
3. **Điều khiển chế độ và tinh chỉnh thông số an toàn**:
   - Chuyển đổi giữa chế độ **Không gạt (`DRY`)** và **Gạt lỗi (`SORT`)**, điều khiển **Chạy (`START`)** / **Dừng (`STOP`)**.
   - Tinh chỉnh trực tiếp độ sáng đèn (`LIGHT`), PWM băng tải (`SPEED`), góc gạt servo (`SERVO_ANGLE`), thời gian giữ gạt (`SERVO_HOLD`) và độ phơi sáng camera (`Exposure`).

Xem ảnh chụp giao diện thực tế tại [`../docs/evidence/dashboard/`](../docs/evidence/dashboard/README.md) và hướng dẫn vận hành tại [`../docs/VAN_HANH.md`](../docs/VAN_HANH.md).

---

## 3. Chạy bộ kiểm thử tự động của phân hệ Dashboard

Từ thư mục gốc của kho mã nguồn:

```bash
# Kiểm tra tạo phiên mới, đánh số lại thứ tự hộp và bảo toàn lịch sử CSV/JSON
python 05_Dashboard/tests/check_runs.py

# Kiểm tra cơ chế đồng bộ thông số mặc định khi dừng và giữ nguyên chỉnh sửa của người vận hành
python 05_Dashboard/tests/check_defaults.py

# Kiểm tra logic xóa ảnh cũ khi đổi phiên, bỏ qua gói tin trễ và kiểm tra cú pháp JavaScript
node 05_Dashboard/tests/check_image.cjs
node --check 05_Dashboard/station/dashboard.js
```
