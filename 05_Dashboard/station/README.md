# Gói điều phối trạm

Gói này phối hợp camera, runtime AI, UART2 và web dashboard. Chạy qua `03_Inference_Pi/run_station.py` từ gốc kho để truyền đúng runtime/profile; production Pi dùng launcher dịch vụ riêng tại `/home/cmh/Pi4_EdgeAI/start_station.sh`.

`run_station.py` điều phối, `station_protocol.py` quản lý bản tin, `dashboard.py` cung cấp API/MJPEG/lịch sử. `startup_defaults.py` chỉ áp dụng mặc định khi dừng/trống. HTML/CSS/JS tại đây là bản giao diện duy nhất trong kho.

REVIEW → ERROR; các kết quả đều gắn phiên/ID. Chỉ chạy một trạm giữ camera/UART. Xem [hướng dẫn module](../README.md) và [vận hành](../../docs/VAN_HANH.md).
