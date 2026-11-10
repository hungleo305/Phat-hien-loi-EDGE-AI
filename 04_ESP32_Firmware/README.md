# Firmware ESP32 — bắt đầu tại đây

ESP-IDF 5.3.5, ESP32. Banner `SINGLE_TASK_UART2_20261109`.
Một task ứng dụng điều khiển motor, servo, hai cảm biến, LED và giao tiếp Pi UART2.
UART0 chỉ xuất log, không nhận lệnh. Bản mới đã build; chưa nạp/nghiệm thu cơ khí.

## Thư mục này chứa gì?

```text
ESP32_Firmware/
├── README.md          Đọc trước
├── main/              Mã nguồn C cần đọc/sửa
├── docs/              Hướng dẫn đấu nối và vận hành
├── build.ps1          Build firmware, KHÔNG nạp thiết bị
├── CMakeLists.txt     Khai báo dự án ESP-IDF
├── sdkconfig          Cấu hình chip/FreeRTOS/driver, cần giữ
├── .vscode/           Cấu hình VS Code, thường không cần sửa
└── .clangd            Cấu hình gợi ý/kiểm tra mã, thường không cần sửa
```

Không còn build trong thư mục mã nguồn. File tự sinh được đặt riêng tại:
`F:\DATN\Cong_cu_phat_trien\outputs\esp32_build`.
Không sửa code trong outputs hoặc Luu_tru.

## Đọc mã theo thứ tự nào?

| File trong main | Vai trò |
|---|---|
| `app_config.h` | GPIO, mức motor/LED, góc servo, các thời gian mặc định |
| `ESP32_Firmware.c` | app_main, một control_task, nhận lệnh dashboard và thực hiện hành động |
| `stopgo.c` / `stopgo.h` | FSM, FIFO hộp, timeout và FAULT |
| `protocol.c` / `protocol.h` | Kiểm tra cú pháp bản tin với Pi |
| `uart.c` / `uart.h` | Gửi/nhận UART2, xử lý lỗi truyền |
| `motor.c` / `motor.h` | Motor L298N và PWM |
| `servo.c` / `servo.h` | PWM góc servo và ước lượng thời gian di chuyển |
| `sensor.c` / `sensor.h` | Đọc GPIO hai cảm biến; debounce nằm trong task điều khiển |
| `led.c` / `led.h` | PWM độ sáng buồng chụp |
| `CMakeLists.txt` | Danh sách file C cần biên dịch |

File `.c` chứa phần thực hiện; `.h` khai báo hàm/kiểu dữ liệu cho các file dùng
chung. Các cặp này có vai trò riêng, không phải bản sao thừa.

Mỗi vòng điều khiển: cảm biến/servo → FSM/FIFO → kiểm heartbeat → nhận tối đa
8 dòng UART2 → gửi trạng thái → nhường CPU 10 ms. Giữ task priority 5,
stack 6144 byte; chỉ task này quản lý trạng thái máy, không cần semaphore ứng dụng.

## Build bằng một lệnh

Mở PowerShell ở thư mục này:

```powershell
.\build.ps1
```

Script dùng các công cụ ESP-IDF đang cài ở `C:\Espressif`; mọi đầu ra dự án
đều ở ổ F. Có thể chạy lại sau khi sửa code. Nếu chỉ muốn sửa/đọc mã,
không cần mở thư mục build.

## Trong build có gì? Vì sao nhiều file?

ESP-IDF biên dịch cả mã của bạn và thư viện nền. Hàng nghìn file được sinh tự
động là bình thường; không phải hàng nghìn file bạn phải đọc hay duy trì.

| File/thư mục trong outputs/esp32_build | Dùng làm gì? |
|---|---|
| `ESP32_Firmware.bin` | Chương trình ứng dụng để nạp |
| `bootloader/bootloader.bin` | Chương trình khởi động chip |
| `partition_table/partition-table.bin` | Bảng bố trí vùng flash |
| `flash_args` / `flasher_args.json` | Địa chỉ và tham số nạp đúng bộ binary |
| `ESP32_Firmware.elf` / `.map` | Debug, tra hàm và phân tích bộ nhớ |
| `compile_commands.json` | Giúp VS Code/clangd hiểu đúng mã nguồn |
| `config/` | Header cấu hình tự sinh từ sdkconfig |
| `esp-idf/`, `CMakeFiles/`, các file còn lại | File trung gian; công cụ tự quản lý |

Không nạp riêng app vào địa chỉ tự đoán; dùng cùng bộ bootloader/partition/app
và tham số nạp. Xem [đấu nối và nạp](docs/DAU_NOI_VA_NAP_CODE.md).

## Vận hành và bản cũ

- [Vận hành/kiểm thử qua dashboard](docs/HUONG_DAN_VAN_HANH_FIFO.md).
- Build cũ, cache, compile_commands cũ và tài liệu thử lịch sử:
  `F:\DATN\Luu_tru\20261109\esp32_sap_xep_thu_muc`; `moves.json` ghi từng mục đã chuyển.
- Công cụ giả lập Pi: `F:\DATN\Luu_tru\20261109\cong_cu_phat_trien_don_dep\work\esp32_uart_tools\mock_pi.py`;
  chỉ thử giao thức, không thay AI hoặc dashboard vận hành.
- Mã nguồn/GPIO/PWM/tham số không thay đổi trong lượt sắp xếp thư mục.
