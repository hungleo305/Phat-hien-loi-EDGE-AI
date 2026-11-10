# Vận hành ESP32 + Pi qua dashboard

Áp dụng cho `Build SINGLE_TASK_UART2_20261109`.
UART0/PL2303 không nhận lệnh nữa; UART0 chỉ còn log chẩn đoán.

## Trước khi chạy

1. Lấy hết hộp khỏi băng tải và hai cảm biến; kiểm nguồn và GND chung.
2. Mở trạm Pi/dashboard, chờ AI/camera và ESP32 READY.
3. Xác nhận STOPPED, motor OFF, FIFO rỗng, cảm biến trống, không FAULT.
4. Chọn DRY (không gạt) trước; chỉnh thông số khi hệ thống dừng và trống.

## Điều khiển hiện có

Dashboard gửi lệnh UART2 có session, sequence và OPACK:

| Lệnh giao thức | Chức năng |
|---|---|
| START / STOP | Chạy hoặc dừng, xóa theo dõi và trả servo home khi STOP |
| DRY / SORT | Không gạt hoặc cho phép gạt hộp DEFECT |
| STATUS | Yêu cầu trạng thái mới |
| SPEED / LIGHT | Đặt PWM motor và đèn |
| SERVO_ANGLE / SERVO_SPEED / SERVO_HOLD | Chỉnh góc và thông số thời gian servo |

Giữ nguyên cú pháp giao thức và điều kiện an toàn. START cần Pi READY,
heartbeat còn mới, cảm biến trống, motor/đèn có mức đặt lớn hơn 0 và servo home.
Các lệnh console `m0/m1`, `reset`, `jog`, `servo0/servo1`, `sv`, `status`
không còn được nhận. Không có chế độ thử motor/servo thủ công qua UART0.
Không mở hai chương trình cùng điều khiển UART2.

## Nghiệm thu sau khi nạp

1. Kiểm banner mới và trạng thái khởi động: STOPPED, motor OFF, sorting OFF.
2. Kiểm chỉ thị hai cảm biến; chỉnh motor/đèn trên dashboard khi dừng.
3. Chạy DRY với chuỗi PASS → DEFECT → PASS; đối chiếu session/ID,
   CAPTURE → CAPTURED → RESULT → DONE và thứ tự FIFO.
4. STOP, lấy hết hộp. Chọn SORT, thử một hộp DEFECT trước rồi chuỗi hộp;
   xác nhận gạt đúng hộp và tay gạt trở về home.
5. Thử mất heartbeat Pi trong điều kiện kiểm soát: motor phải dừng
   sau ngưỡng 2 giây cộng độ trễ vòng điều khiển.
6. Kiểm timeout/lỗi AI dẫn tới FAULT; không được chuyển ERROR/REVIEW thành PASS.

Khi FAULT, ghi lại trạng thái/log. Ngắt nguồn công suất nếu cần chạm cơ khí,
lấy hết hộp và làm trống cảm biến trước khi dùng STOP trên dashboard để xóa
theo dõi/trả home. Chờ servo hoàn tất rồi mới START. Nếu mất liên lạc,
khôi phục kết nối hoặc khởi động lại với băng tải trống.

Không kết luận servo đã tới góc thật chỉ từ log: SG90 không có phản hồi góc/lực.
Tham số SERVO_SPEED chỉ tham gia ước lượng thời gian; bản hiện tại ra lệnh
PWM tới góc đích trực tiếp, không điều khiển tốc độ vật lý bằng phản hồi.

## Mặc định giữ nguyên

- Motor 160/255; LED 30/255; góc gạt 35°; tham số servo 230°/s.
- Chờ ổn định trước chụp 250 ms; debounce 30 ms.
- UART2 GPIO17/TX, GPIO16/RX, 115200, TTL 3,3 V.
- Giá trị dashboard chỉ áp dụng cho phiên khởi động;
  `main/app_config.h` chứa mặc định.
