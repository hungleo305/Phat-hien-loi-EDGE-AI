# Phân hệ 04 — Firmware điều khiển thời gian thực trên ESP32

Thư mục này chứa mã nguồn firmware C phát triển trên khung **ESP-IDF v5.3.5** cho vi điều khiển **ESP32-WROOM-32** (phiên bản định danh `SINGLE_TASK_UART2_20261109`).

---

## 1. Nhiệm vụ của ESP32 trong hệ thống

ESP32 đảm nhận toàn bộ phần điều khiển phần cứng thời gian thực theo chu trình **Stop & Go** và quản lý hàng đợi **FIFO** (xem lưu đồ tại [`../docs/diagrams/esp32_chu_trinh_mot_hop.png`](../docs/diagrams/esp32_chu_trinh_mot_hop.png)):

1. **Quét cảm biến và dừng chụp ảnh**: Đọc cảm biến quang tại buồng chụp (`GPIO18`, chống dội `30 ms`). Khi phát hiện hộp, chờ ổn định `250 ms`, dừng động cơ băng tải, cấp mã `ID` mới vào hàng đợi **FIFO** và gửi bản tin `CAPTURE <session> <id>` qua **UART2** (`115200 bps`) lên Raspberry Pi 4.
2. **Cho băng tải chạy tiếp ngay sau khi chụp**: Ngay khi nhận được phản hồi `CAPTURED` hợp lệ từ Pi (tối đa `2000 ms`), ESP32 đánh dấu hộp đã chụp và cho phép băng tải chạy lại ngay trong lúc Pi đang xử lý AI.
3. **Nhận kết quả và phân loại tại cửa gạt**:
   - Bản tin `RESULT <session> <id> PASS|DEFECT|ERROR` từ Pi (hạn chờ `5000 ms`) được ghi vào đúng phần tử trong hàng đợi FIFO.
   - Khi hộp đi tới cảm biến hồng ngoại tại cửa gạt (`GPIO19`), ESP32 kiểm tra phần tử đầu hàng đợi FIFO:
     - Nếu chưa có kết quả AI: tạm dừng băng tải chờ kết quả.
     - Nếu là **`DEFECT`** và đang bật chế độ phân loại (`SORT`): quay servo SG90 (`GPIO13`) tới góc gạt (mặc định trạm đặt `60°`, giữ `350 ms`) để đẩy hộp lỗi sang nhánh loại, sau đó thu tay gạt về vị trí chuẩn (`0°`).
     - Nếu là **`PASS`** (hoặc đang ở chế độ `DRY`): cho hộp đi thẳng qua cửa gạt.
     - Khi hộp rời cảm biến cửa gạt và hoàn tất pha gạt, ESP32 gửi bản tin `DONE` và xóa hộp đầu khỏi FIFO.
4. **Giám sát an toàn (Heartbeat & Fault)**: Nếu mất tín hiệu `HEARTBEAT` từ Pi quá `2 giây`, quá hạn chờ `CAPTURE`/`RESULT`, quá hạn di chuyển tới cửa gạt (`15000 ms`) hoặc nhận kết quả `ERROR`, ESP32 lập tức dừng băng tải và chuyển sang trạng thái `FAULT`.

---

## 2. Cấu trúc mã nguồn và sơ đồ chân GPIO

### Danh mục tệp trong [`main/`](main/)

| Tệp mã nguồn | Chức năng |
|---|---|
| [`app_config.h`](main/app_config.h) | Định nghĩa sơ đồ chân GPIO, tốc độ UART2 (`115200`), các ngưỡng thời gian timeout và thông số mặc định. |
| [`ESP32_Firmware.c`](main/ESP32_Firmware.c) | Hàm `app_main` và vòng lặp điều khiển đơn tác vụ (`control_task`) đồng bộ cảm biến, FSM/FIFO, thiết bị chấp hành và UART2. |
| [`stopgo.c`](main/stopgo.c), [`stopgo.h`](main/stopgo.h) | Máy trạng thái hữu hạn (FSM), hàng đợi hộp FIFO, kiểm tra điều kiện an toàn và xử lý trạng thái lỗi `FAULT`. |
| [`protocol.c`](main/protocol.c), [`protocol.h`](main/protocol.h), [`uart.c`](main/uart.c), [`uart.h`](main/uart.h) | Phân tích cú pháp bản tin lệnh/trạng thái (`START`, `STOP`, `DRY`, `SORT`, `RESULT`, `OPACK`...) và giao tiếp UART2. |
| [`motor.c`](main/motor.c), [`led.c`](main/led.c), [`servo.c`](main/servo.c), [`sensor.c`](main/sensor.c) (và `.h`) | Trình điều khiển phần cứng: động cơ DC và đèn LED qua mạch cầu H L298N (LEDC PWM), servo SG90 và lọc nhiễu cảm biến. |

### Bảng phân bổ chân GPIO trên ESP32-WROOM-32

| Khối thiết bị | Chân ESP32 | Kết nối phần cứng | Ghi chú cấu hình |
|---|---|---|---|
| **Động cơ băng tải (L298N Kênh A)** | `GPIO27` (`IN1`), `GPIO26` (`IN2`), `GPIO14` (`ENA`) | Mạch L298N -> Động cơ DC 24 V | Tháo jumper `ENA` để điều khiển tốc độ bằng PWM |
| **Đèn buồng chụp (L298N Kênh B)** | `GPIO32` (`IN3`), `GPIO33` (`IN4`), `GPIO25` (`ENB`) | Mạch L298N -> Đèn LED 24 V | Tháo jumper `ENB` để điều chỉnh độ sáng bằng PWM |
| **Cơ cấu gạt phân loại** | `GPIO13` (Xung PWM) | Dây tín hiệu Servo SG90 | Nguồn 5 V cấp từ mạch hạ áp LM2596 (không lấy từ chân 3V3 ESP32) |
| **Hai cảm biến phát hiện hộp** | `GPIO18` (Chụp), `GPIO19` (Cửa gạt) | Ngõ ra số `DO` của 2 cảm biến | Mức logic `LOW` khi có hộp, `HIGH` khi trống; chống dội `30 ms` |
| **Giao tiếp với Raspberry Pi 4** | `GPIO17` (`TX2`), `GPIO16` (`RX2`), `GND` | Chân `GPIO15 (RXD)`, `GPIO14 (TXD)`, `GND` của Pi 4 | Giao tiếp UART2 mức logic `3,3 V TTL`, tốc độ `115200 bps` |

Xem sơ đồ nguyên lý tại [`../docs/diagrams/dau_noi_va_nguon.png`](../docs/diagrams/dau_noi_va_nguon.png) và tài liệu chi tiết:
- [Hướng dẫn đấu nối phần cứng và nạp firmware (`docs/DAU_NOI_VA_NAP_CODE.md`)](docs/DAU_NOI_VA_NAP_CODE.md)
- [Quy trình kiểm tra và vận hành hàng đợi FIFO (`docs/HUONG_DAN_VAN_HANH_FIFO.md`)](docs/HUONG_DAN_VAN_HANH_FIFO.md)

---

## 3. Hướng dẫn biên dịch (Build) Firmware

Từ thư mục gốc của kho mã nguồn trên Windows (sử dụng bộ công cụ ESP-IDF v5.3.5 cài tại `C:/Espressif`):

```powershell
./04_ESP32_Firmware/build.ps1
```

Kịch bản `build.ps1` sẽ biên dịch bản nhị phân ra thư mục `F:/DATN/Cong_cu_phat_trien/outputs/esp32_build` mà không làm phát sinh tệp rác trong kho Git. Trên máy tính khác đã kích hoạt môi trường ESP-IDF 5.3.5, có thể chạy trực tiếp `idf.py -B <thu_muc_build> build` tại thư mục `04_ESP32_Firmware`.
