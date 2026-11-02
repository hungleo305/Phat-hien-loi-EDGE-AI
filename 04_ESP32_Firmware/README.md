# THƯ MỤC 04: CODE VI ĐIỀU KHIỂN ESP32 (FIRMWARE)

> **Ánh xạ thuyết minh đồ án:** Mục 3.3.1 (Lập trình vi điều khiển ESP32 - FreeRTOS, FSM Stop & Go, PWM và Servo).

---

## 1. Danh sách các tệp trong thư mục

| Tên tệp | Vai trò |
|---|---|
| **`main/ESP32_Firmware.c`** | **Mã nguồn C chính:** Khởi tạo các chân GPIO, thiết lập 2 tác vụ FreeRTOS (`control_task` ưu tiên 5, `console_task` ưu tiên 4) và hàm `app_main`. |
| **`main/motor.c` & `motor.h`** | Điều khiển động cơ băng tải DC qua mạch cầu H (LEDC PWM 20 kHz) với thuật toán tăng tốc mềm (Ramp-up/Ramp-down) chống giật quán tính sản phẩm. |
| **`main/servo.c` & `servo.h`** | Điều khiển cánh gạt phân loại SG90 bằng **profile 3 bước dứt khoát** ($0^\circ \rightarrow 12^\circ \rightarrow 23^\circ \rightarrow 35^\circ$ trong 150 ms) triệt tiêu rung giật vùng chết analog (deadband). |
| **`main/sensor.c` & `sensor.h`** | Đọc tín hiệu 2 cảm biến quang NPN (chụp ảnh & phân loại) với thuật toán lọc chống nhiễu tiếp điểm (Debounce 30 ms). |
| **`main/protocol.c` & `protocol.h`** | Bộ phân tích cú pháp UART ASCII giao tiếp với Raspberry Pi (`HELLO`, `READY`, `CAPTURE`, `RESULT`). |
| **`main/led.c` & `led.h`** | Điều khiển độ sáng đèn LED chiếu sáng sản phẩm bằng điều chế độ rộng xung PWM. |
| **`CMakeLists.txt` & `sdkconfig`** | Tệp cấu hình dự án chuẩn ESP-IDF phiên bản 5.3.5. |
| **`build/ESP32_Firmware.bin`** | **Bản nhị phân đã biên dịch sẵn**, có thể nạp thẳng vào ESP32 qua cổng COM bằng công cụ `esptool.py`. |

---

## 2. Máy trạng thái hữu hạn Stop & Go (10 trạng thái)

Firmware hiện thực hóa FSM chuẩn công nghiệp gồm 10 trạng thái:
1. `SG_STOPPED`: Trạm dừng an toàn, động cơ tắt.
2. `SG_STARTING`: Bắt đầu khởi động, kiểm tra cảm biến.
3. `SG_RUNNING`: Băng tải đang chạy kéo sản phẩm vào vùng chụp.
4. `SG_STOPPING_FOR_CAPTURE`: Phát hiện hộp tại cảm biến chụp, hãm phanh mềm động cơ.
5. `SG_SETTLING`: Dừng chờ 150 ms để triệt tiêu dao động cơ học trước khi chụp.
6. `SG_WAIT_CAPTURE`: Gửi lệnh `CAPTURE` qua UART và chờ Pi chụp ảnh xong.
7. `SG_WAIT_DECISION`: Động cơ tiếp tục chạy đưa hộp về phía phân loại, đồng thời chờ kết quả AI từ Pi.
8. `SG_SORTING_DEFECT`: Kích hoạt servo gạt hộp lỗi sang khay DEFECT.
9. `SG_SORTING_PASS`: Mở đường cho hộp đạt tiêu chuẩn đi thẳng qua khay PASS.
10. `SG_FAULT`: Trạng thái dừng khẩn cấp khi phát hiện lỗi kẹt hộp hoặc mất đồng bộ.

---

## 3. Lệnh nạp Flash vào ESP32

```powershell
# Nạp trực tiếp qua cổng COM (ví dụ COM3)
esptool.py --chip esp32 -p COM3 -b 460800 write_flash 0x10000 build/ESP32_Firmware.bin
```

