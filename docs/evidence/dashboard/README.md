# Dashboard đang sử dụng

Các ảnh dưới đây chụp ngày 12/11/2026 từ giao diện laptop kết nối thật tới Pi và ESP32. Trạm ở trạng thái dừng; chỉ xem lịch sử và mở cài đặt, không chạy hộp mới để tạo dữ liệu minh họa.

| Ảnh | Nội dung |
|---|---|
| [dashboard_overview.jpg](dashboard_overview.jpg) | Trạng thái trạm và bộ đếm khi xem phiên lịch sử #6 |
| [dashboard_settings.jpg](dashboard_settings.jpg) | Mức LED 70/255, PWM 180/255, góc đặt 60°, chờ thu 350 ms, phơi sáng camera 1100 |
| [dashboard_history.jpg](dashboard_history.jpg) | Một phần lịch sử #6; ảnh camera trực tiếp và vùng kết quả của trạm hiện tại |

Khi mở phiên cũ, bộ đếm và bảng lịch sử phản ánh phiên đang xem; trạng thái thiết bị và camera vẫn là trạng thái hiện tại. Vì vậy bộ đếm lịch sử có thể khác số hộp của phiên thiết bị hiện hành.

Mã nguồn: [giao diện](../../../05_Dashboard/), [chương trình trạm](../../../05_Dashboard/station/). Các ảnh là nguồn minh họa cho báo cáo, không phải phép đo độ trễ hiển thị. Khi chèn vào Word có thể cắt vùng hiển thị bằng định dạng ảnh mà không thay đổi ảnh gốc.
