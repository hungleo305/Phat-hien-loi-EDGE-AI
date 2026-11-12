# Hướng dẫn vận hành hệ thống kiểm định hộp

Tài liệu này hướng dẫn quy trình khởi động, vận hành, giám sát và xử lý tình huống trên mô hình băng tải thực tế kết nối giữa **Raspberry Pi 4**, **ESP32** và **Web Dashboard**.

---

## 1. Truy cập giao diện điều khiển (Web Dashboard)

Hệ thống trên Raspberry Pi 4 được quản lý tự động bởi dịch vụ nền `datn-station.service` ngay sau khi bật nguồn. Mở trình duyệt web không tự động làm chạy băng tải.

- **Truy cập trực tiếp trên màn hình Raspberry Pi 4**:
  Mở biểu tượng **DATN Dashboard** ngoài màn hình Desktop hoặc truy cập địa chỉ:
  `http://127.0.0.1:8768`
- **Truy cập từ Laptop giám sát trong mạng nội bộ**:
  Mở lối tắt `MO_DASHBOARD_DATN.lnk` trên laptop để khởi tạo kết nối SSH tunnel tới Pi (`pi4-edgeai.local`), sau đó trình duyệt sẽ tự động mở tại địa chỉ:
  `http://127.0.0.1:8769`

---

## 2. Thông số mặc định khi khởi động trạm

Khi dịch vụ trạm trên Pi kết nối với ESP32 ở trạng thái dừng (`STOPPED`), hai cảm biến đều trống và hệ thống không có lỗi, trạm tự động đồng bộ bộ thông số chuẩn đã hiệu chỉnh thực nghiệm:

| Thông số | Giá trị mặc định | Ý nghĩa kỹ thuật |
|---|---|---|
| **Mức sáng đèn (`LIGHT`)** | `70 / 255` | Độ rộng xung PWM cấp cho đèn LED buồng chụp 24 V qua L298N |
| **Tốc độ băng tải (`SPEED`)** | `180 / 255` | Độ rộng xung PWM cấp cho động cơ DC 24 V qua L298N |
| **Góc gạt servo (`SERVO_ANGLE`)** | `60°` | Góc quay lệnh của tay gạt servo SG90 khi đẩy hộp lỗi (`0°` là vị trí thu song song băng tải) |
| **Thời gian giữ gạt (`SERVO_HOLD`)** | `350 ms` | Thời gian giữ tay gạt ở vị trí đẩy trước khi thu về vị trí chuẩn |
| **Phơi sáng camera (`Exposure`)** | `1100` | Giá trị `exposure_time_absolute` trong `camera_profile.json` giúp giảm nhòe chuyển động |

*Lưu ý*: Nếu người vận hành chủ động thay đổi thông số trên giao diện trong phiên làm việc, hệ thống sẽ giữ nguyên giá trị người vận hành đã chọn mà không tự động ghi đè lại.

---

## 3. Quy trình vận hành chuẩn một phiên kiểm định

1. **Kiểm tra an toàn trước khi chạy**:
   - Đảm bảo mặt băng tải, vùng buồng chụp và cửa gạt thông thoáng, lấy hết các hộp còn tồn đọng.
   - Kiểm tra nguồn 24 V (cấp cho động cơ, đèn và mạch hạ áp 5 V) và nguồn riêng 5,1 V – 3 A của Raspberry Pi 4.
2. **Xác nhận trạng thái sẵn sàng trên Dashboard**:
   - Các chỉ báo kết nối **Pi / Camera / AI / ESP32** đều ở trạng thái sẵn sàng (`READY`).
   - Trạng thái máy đang là `STOPPED`, hàng đợi `FIFO = 0`, hai cảm biến báo trống, không có cảnh báo `FAULT`.
3. **Tạo phiên làm việc mới (`New Run`)**:
   - Nhập tên phiên (hoặc dùng mã tự động) và nhấn tạo phiên mới để đặt lại bộ đếm (`PASS`, `DEFECT`, `ERROR`) về `0` và xóa ảnh cũ trên màn hình chính (dữ liệu các phiên trước vẫn được lưu nguyên vẹn trong mục Lịch sử).
4. **Chọn chế độ làm việc và khởi chạy**:
   - Chọn **Không gạt (`DRY`)** nếu chỉ muốn kiểm tra nhận diện và thu thập dữ liệu, hoặc chọn **Gạt lỗi (`SORT`)** để kích hoạt servo phân loại hộp `DEFECT`.
   - Nhấn **Chạy (`START`)** và đặt từng hộp lên đầu băng tải với khoảng cách hợp lý (đảm bảo hộp trước đã rời vùng chụp trước khi hộp sau đi vào).
5. **Theo dõi và kết thúc phiên**:
   - Quan sát ảnh chụp, khung bao dự đoán, lý do kết luận và thao tác gạt tại cửa phân loại.
   - Khi hoàn tất, nhấn **Dừng (`STOP`)** và tải tệp báo cáo của phiên dưới định dạng **CSV** hoặc **JSON** để lưu trữ.

---

## 4. Quy tắc xử lý lỗi và khôi phục an toàn

- **Quy tắc an toàn đối với kết quả `REVIEW` / `ERROR`**: Khi ảnh chụp bị mờ, hộp bị che khuất hoặc thông tin trên tem không đủ độ tin cậy (`REVIEW`), trạm điều phối chuyển bản tin UART thành `ERROR`. Hệ thống tuyệt đối không tự động cho qua như hộp đạt (`PASS`).
- **Khi xảy ra `FAULT` (quá thời gian chờ chụp/xử lý AI, kẹt hộp tại cửa gạt hoặc mất tín hiệu heartbeat)**:
  1. Băng tải sẽ tự động dừng ngay lập tức.
  2. Lấy toàn bộ hộp ra khỏi băng tải, kiểm tra nguyên nhân vật lý (vị trí hộp, cảm biến hoặc nguồn).
  3. Nhấn lệnh **Dừng (`STOP`)** trên Dashboard để xóa hàng đợi FIFO, đặt lại máy trạng thái và đưa servo về vị trí chuẩn (`0°`).
  4. Chỉ nhấn **Chạy (`START`)** trở lại khi các chỉ báo đã xanh và hai cảm biến hoàn toàn trống.

---

## 5. Các lệnh kiểm tra dịch vụ trực tiếp trên Raspberry Pi 4

Khi cần chẩn đoán kỹ thuật qua SSH trên Raspberry Pi 4:

```bash
# Kiểm tra trạng thái dịch vụ trạm
systemctl --user status datn-station.service

# Kiểm tra gói phần mềm đang được trỏ chạy
readlink -f /home/cmh/Pi4_EdgeAI/current

# Truy vấn nhanh trạng thái JSON từ API cục bộ
curl http://127.0.0.1:8768/api/state

# Xem 50 dòng nhật ký vận hành gần nhất
journalctl --user -u datn-station.service -n 50 --no-pager
```

*Lưu ý*: Khi dịch vụ `datn-station.service` đang chạy và giữ quyền truy cập cổng Camera (`/dev/video0`) cùng cổng UART2 (`/dev/serial0`), không khởi chạy chồng thêm một tiến trình `run_station.py` thứ hai.
