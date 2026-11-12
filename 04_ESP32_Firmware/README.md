# Firmware điều khiển ESP32

ESP-IDF 5.3.5, ESP32-WROOM-32; banner `SINGLE_TASK_UART2_20261109`. Một task điều khiển đọc hai cảm biến, quản lý FSM/FIFO, điều khiển motor/LED/servo và trao đổi với Pi qua UART2. UART0 chỉ xuất log. Người vận hành đã xác nhận nạp firmware; gạt hộp đã được quan sát trong các đợt chạy thử, chưa có nghiệm thu dài hạn.

## Thứ tự đọc mã

| Tệp trong main | Nội dung |
|---|---|
| `app_config.h` | GPIO, PWM, thời gian và giới hạn mặc định firmware |
| `ESP32_Firmware.c` | `app_main`, control_task, cập nhật thiết bị và UART |
| `stopgo.c` / `.h` | Máy trạng thái, hàng đợi hộp, timeout và FAULT |
| `protocol.c` / `.h`, `uart.c` / `.h` | Cú pháp và truyền bản tin UART2 |
| `motor.c`, `led.c`, `servo.c`, `sensor.c` và `.h` | Driver từng thiết bị |

Tệp `.h` là khai báo cho các tệp `.c` dùng chung, không phải bản sao thừa. Mỗi vòng control_task cập nhật cảm biến/servo, FSM/FIFO, heartbeat, nhận UART, gửi trạng thái rồi nhường CPU.

Sau CAPTURED hợp lệ, băng tải được chạy tiếp trong lúc AI xử lý; chỉ chờ kết quả tại cửa gạt khi cần. RESULT phải khớp phiên và ID. REVIEW/ERROR không trở thành PASS. Mất liên lạc hoặc FAULT yêu cầu người vận hành xử lý trước khi START lại.

## Build trên laptop hiện tại

Từ gốc kho:

```powershell
./04_ESP32_Firmware/build.ps1
```

Script sử dụng ESP-IDF ở `C:/Espressif`; đầu ra ở `F:/DATN/Cong_cu_phat_trien/outputs/esp32_build`. Script chỉ build, không flash. Trên máy khác, cấu hình ESP-IDF 5.3.5 rồi chạy `idf.py -B <thu_muc_build> build` trong module này. `sdkconfig` và `main/CMakeLists.txt` là đầu vào cần giữ.

Khi nạp, dùng đúng bộ bootloader, partition, app và địa chỉ trong `flasher_args.json`, không đoán địa chỉ flash. [Đấu nối và nạp](docs/DAU_NOI_VA_NAP_CODE.md) và [vận hành FIFO](docs/HUONG_DAN_VAN_HANH_FIFO.md) giải thích phần cứng, bản tin và khôi phục sau lỗi.

Thông số trong firmware khi chạy riêng có thể khác cấu hình Pi áp dụng lúc khởi động (PWM 180, LED 70, góc 60°, chờ thu 350 ms). Servo không có phản hồi vị trí; tham số tốc độ cũ chỉ dùng ước lượng timeout, không bảo đảm thay đổi tốc độ quay thực.
