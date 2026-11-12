# Vận hành mô hình hiện tại

## Mở giao diện

Trên laptop, mở `F:/DATN/MO_DASHBOARD_DATN.lnk`; gateway phục vụ `http://127.0.0.1:8769` và tạo SSH tunnel tới Pi. Pi hiện được tìm qua `pi4-edgeai.local` hoặc địa chỉ IP đã cấu hình. Khóa SSH chỉ giữ trên máy vận hành.

Trên Pi, mở shortcut dashboard ở desktop hoặc truy cập `http://127.0.0.1:8768`. Dịch vụ tự chạy sau khi Pi khởi động; mở giao diện không khởi động motor.

## Một lượt vận hành

1. Kiểm tra nguồn, buồng chụp, vị trí cảm biến và đường gạt; lấy hết hộp còn kẹt.
2. Xác nhận Pi/camera/AI/ESP32 sẵn sàng, motor dừng, không FAULT, hai cảm biến trống.
3. Kiểm tra LED/PWM/camera/góc gạt và thời gian chờ thu; tạo phiên có tên để lưu dữ liệu.
4. Chọn Không gạt khi kiểm nhận diện hoặc Gạt lỗi khi thử phân loại; bấm chạy rồi cấp hộp theo khoảng cách phù hợp.
5. Đối chiếu ảnh, kết luận và hộp tại cửa gạt. Khi xong, bấm dừng và tải CSV/JSON của phiên cần lưu.

REVIEW được xử lý thành ERROR, không phải PASS. Khi FAULT hoặc mất liên lạc, lấy hộp ra, kiểm nguyên nhân, gửi STOP để xóa theo dõi/đưa cơ cấu về ban đầu, rồi chỉ START khi các điều kiện sẵn sàng được đáp ứng.

## Kiểm tra dịch vụ trên Pi

```bash
systemctl --user status datn-station.service
readlink -f /home/cmh/Pi4_EdgeAI/current
curl http://127.0.0.1:8768/api/state
journalctl --user -u datn-station.service -n 50 --no-pager
```

Runtime: `/home/cmh/Pi4_EdgeAI/current/runtime`; station: `current/station`; khởi động: `/home/cmh/Pi4_EdgeAI/start_station.sh`. Không chạy thêm một station khi dịch vụ đang giữ camera/UART.

## Giới hạn đo lường

Thời gian AI là thời gian hàm kiểm định. CAPTURE-to-RESULT còn gồm thu ảnh và điều phối; thời gian hiển thị trên trình duyệt có thêm chu kỳ cập nhật. Các số này không phải toàn bộ chu kỳ băng tải/gạt hoặc năng suất hộp/phút. Servo hiện chưa có phản hồi vị trí và PWM không phải vận tốc đo trực tiếp.
