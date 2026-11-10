# Dashboard
Máy chủ HTTP và giao diện của trạm Pi. server.py cung cấp lớp Dashboard, không phải lệnh khởi động độc lập. Trạm production khởi động qua service trên Pi.
Giao diện cập nhật trạng thái mỗi 1500 ms. DRY là chạy thử không gạt; SORT cho phép gạt DEFECT. Độ trễ hiển thị là CAPTURE-to-RESULT, không bao gồm thời gian trình duyệt hiển thị.
