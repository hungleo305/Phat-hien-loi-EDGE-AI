# Suy luận trên Pi
runtime/ là gói hiện hành được đồng bộ và kiểm SHA-256 từ Pi. Model production là NCNN FP32.
Kiểm tra: `python runtime/self_check.py --backend ncnn`.
Chạy trạm trên Pi với camera/UART phù hợp: `python run_station.py --headless --dashboard --dashboard-local-trust`.
Chỉ chạy sau khi dừng trạm khác đang giữ camera/UART; lệnh này không tự triển khai hay thay service production.
Các file Python ở gốc là bản trình bày logic tương ứng; dùng runtime/ làm đường kiểm thử chuẩn.
