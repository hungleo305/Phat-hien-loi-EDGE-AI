# Đấu nối và nạp ESP32 Stop&Go — cấu hình 24 V

Cập nhật 21/10/2026 theo linh kiện người dùng xác nhận: ESP32 30 pin/WROOM, L298N, nguồn 24 V, bộ hạ áp, hai cảm biến module LM393, motor 24 V, đèn buồng 24 V, servo SG90. Firmware/chân GPIO đã đọc lại, không thay trong lần viết hướng dẫn này.

**Chưa biết mã bộ hạ áp, dòng motor/đèn, ảnh jumper L298N và mã module cảm biến.** Bảng dưới dùng tên chân in trên module L298N thông dụng; nếu tên chân hoặc jumper khác thì đối chiếu ảnh trước khi cấp nguồn. Điện áp phù hợp không có nghĩa dòng tải và nhiệt L298N đã đạt.

## A. Phân phối nguồn

Tắt nguồn trước khi đấu. Chỉnh và đo đầu ra bộ hạ áp khi chưa nối tải.

```text
Nguồn 24 V (+) ──┬── VS / +12V (chân nguồn tải) của L298N
                 └── IN+ bộ hạ áp 24 V → khoảng 5 V

Nguồn 24 V (−) ───── GND chung

Hạ áp OUT+ ~5 V ──┬── chân +5V LOGIC L298N (đã tháo jumper ổn áp)
                  └── dây nguồn servo SG90, theo định mức servo thực tế

ESP32: lượt nạp/thử cấp nguồn bằng USB laptop
Pi: nguồn riêng đúng chuẩn Pi
Tất cả nối GND tín hiệu chung; không nối các đường +5V nguồn độc lập với nhau.
```

- Không cấp 24 V vào VIN/5V/3V3 ESP32, GPIO, cảm biến LM393 hoặc SG90.
- Không dùng chân 3V3 ESP32 để cấp servo. Đường nguồn servo lấy từ hạ áp, không đi qua board ESP32.
- Khi USB laptop cấp ESP32, chưa nối thêm OUT+ hạ áp vào VIN/5V ESP32. Chỉ nối chung GND.
- Dây hồi dòng motor/servo đi về GND nguồn/hạ áp; tránh cho dòng công suất đi xuyên đường GND mảnh của ESP32. Chung GND không có nghĩa lấy board ESP32 làm điểm đi qua của toàn bộ dòng tải.
- Bộ hạ áp phải nhận được 24 V và đủ dòng tải/đỉnh dòng servo. Nếu servo hoạt động làm ESP32 reset thì kiểm tra nguồn và dây trước.
- Nguồn điện lưới đầu vào của bộ nguồn 24 V phải được che kín/đấu sẵn phù hợp; hướng dẫn này áp dụng phần DC đầu ra.

## B. Jumper L298N — phân biệt ba jumper

| Jumper | Trong cấu hình này |
|---|---|
| 5V-EN / jumper bật ổn áp trên board | Tháo khi cấp VS=24 V trên module kiểu phổ biến có ổn áp tích hợp; cấp 5 V logic ngoài |
| ENA, cạnh IN1/IN2 | Tháo để GPIO14 điều khiển PWM |
| ENB, cạnh IN3/IN4 | Tháo để GPIO25 điều khiển PWM |

Jumper 5V-EN không phải ENA/ENB. Không đoán vị trí theo màu board. Tham khảo đúng nhãn chân/tài liệu module; [Joy-IT](https://joy-it.net/files/files/Produkte/SBC-MotorDriver2/SBC-MotoDriver2_Manual_2024-05-08.pdf) yêu cầu bỏ jumper ổn áp khi VS >12 V; [Handson](https://handsontec.com/dataspecs/module/L298N%20Motor%20Driver.pdf) minh họa cấp logic 5 V ngoài khi jumper ổn áp tháo.

Chân nguồn tải trên board có thể ghi +12V nhưng thực chất là VS; chỉ đưa 24 V vào nếu module/linh kiện trên board hỗ trợ 24 V. Chân +5V logic hoàn toàn khác chân VS.

## C. ESP32 → L298N → motor và đèn

GPIO là số in trên ESP32 (D27/IO27…), không phải vị trí chân thứ 27 trong hàng 30 chân.

| ESP32 | L298N | Chức năng |
|---|---|---|
| GPIO27 | IN1 | Chiều motor |
| GPIO26 | IN2 | Chiều motor |
| GPIO14 | ENA | PWM motor, tháo jumper ENA |
| GPIO32 | IN3 | Kênh đèn |
| GPIO33 | IN4 | Kênh đèn |
| GPIO25 | ENB | PWM đèn, tháo jumper ENB |
| GND | GND | Mốc tín hiệu chung |

| Tải | Ngõ ra L298N |
|---|---|
| Hai dây motor 24 V | OUT1 và OUT2 |
| Đèn buồng 24 V cực + | OUT3 |
| Đèn buồng 24 V cực − | OUT4 |

Đèn nối giữa OUT3/OUT4, không đổi dây âm đèn về GND nếu vẫn dùng đúng mạch H-bridge này. Với IN3 HIGH/IN4 LOW của code, OUT3 là phía dương so với OUT4. Đèn phải là cụm đèn thiết kế nhận nguồn 24 V, không phải LED trần thiếu hạn dòng.

L298N có sụt áp và tỏa nhiệt; motor/đèn không nhận đủ 24 V lý tưởng. Kiểm tra dòng motor khi khởi động/kẹt và dòng đèn so với khả năng thực tế của board; không dựa vào dòng nguồn 24 V để kết luận driver chịu được. Điện trở kéo xuống khoảng 10 kΩ ở ENA và ENB có thể giúp giữ disable khi GPIO chưa khởi tạo; cần đấu đúng GND.

## D. Hai cảm biến LM393

LM393 là tên comparator, chưa xác định đầy đủ module; một số board khác nhau về nguồn và pull-up DO.

Nếu module ghi hỗ trợ **3,3–5 V**, thử cấp bằng 3V3 ESP32 để DO không bị kéo lên 5 V:

| Cảm biến | Chân module | Nối |
|---|---|---|
| Buồng chụp | VCC | 3V3 ESP32, khi module hỗ trợ 3,3 V |
| Buồng chụp | GND | GND chung |
| Buồng chụp | DO/OUT số | GPIO18 |
| IR cửa gạt | VCC | 3V3 ESP32, khi module hỗ trợ 3,3 V |
| IR cửa gạt | GND | GND chung |
| IR cửa gạt | DO/OUT số | GPIO19 |

Không dùng chân AO cho firmware này. Không đưa 24 V vào cảm biến. Nếu phải cấp module 5 V, cần xác nhận mạch DO và chuyển mức phù hợp trước khi nối ESP32; không nối DO kéo lên 5 V trực tiếp. [Datasheet ESP32](https://documentation.espressif.com/esp32_datasheet_en.html).

Code mong muốn không có hộp=HIGH, có hộp=LOW. Nếu module hoạt động ngược hoặc không đủ khoảng cách ở 3,3 V, xử lý đúng phần cứng/cấu hình trước khi chạy băng tải.

## E. Servo SG90

| Dây SG90 thường gặp | Nối |
|---|---|
| Đỏ | Nguồn hạ áp theo định mức servo, khoảng 5 V; đo trước |
| Nâu/đen | GND chung |
| Cam/vàng | GPIO13 |

Kiểm tra nhãn/thứ tự dây đúng servo thực tế, không suy ra chỉ từ màu. [TowerPro SG90](https://towerpro.com.tw/product/sg90-7/) công bố điện áp hoạt động 4,8 V; bản clone cần đối chiếu thông số riêng. Chưa gắn tay gạt chịu tải khi chưa kiểm vị trí home. Mặc định DRY không kích gạt, nhưng servo_init vẫn phát xung home lúc bật nguồn.

## F. Giao tiếp và nạp — cập nhật 09/11/2026

UART0 chỉ còn log chẩn đoán; không còn nhập status/m0/m1 hoặc lệnh thử servo.
PL2303 không cần cho vận hành thường ngày. Dùng dashboard Pi qua UART2.

| ESP32 | Pi 4 header 40 pin |
|---|---|
| GPIO17/TX2 | GPIO15/RXD, chân vật lý 10 |
| GPIO16/RX2 | GPIO14/TXD, chân vật lý 8 |
| GND | GND, ví dụ chân vật lý 6 |

UART TTL 3,3 V, 115200. Không nối đường 5 V/24 V giữa hai board.
Không để Pi và adapter khác cùng phát vào RX2.

Để build, chạy `build.ps1` tại thư mục firmware. Build không tự nạp.
Để nạp khi có phần cứng, đóng monitor đang giữ COM, thay COM5 bằng cổng board:

```powershell
cd F:\DATN\Tai_nguyen\ESP32_Firmware
# Build trước để thiết lập môi trường trong PowerShell này.
.\build.ps1
& 'C:\Espressif\python_env\idf5.3_py3.12_env\Scripts\python.exe' `
  'C:\Espressif\frameworks\esp-idf-v5.3.5\tools\idf.py' `
  -C . -B 'F:\DATN\Cong_cu_phat_trien\outputs\esp32_build' -p COM5 flash
```

Chỉ dùng bộ bootloader/partition/app từ cùng build. Nếu cần BOOT thủ công:
giữ BOOT, nhấn nhả EN, thả BOOT khi bắt đầu ghi. Không dùng erase_flash để nạp thường.

Log boot phải có `SINGLE_TASK_UART2_20261109`, STOPPED, sorting OFF.
Servo có thể về home khi bật nguồn nên để cơ khí trống.
Nghiệm thu cảm biến, LED, motor, FIFO, servo, heartbeat và FAULT theo
[hướng dẫn vận hành](HUONG_DAN_VAN_HANH_FIFO.md). Khởi đầu DRY rồi mới SORT;
không dùng các lệnh UART0 trong tài liệu lịch sử.
