# Station V4 2026-10-29

Đây là lớp điều phối trạm Pi dùng model trong
`/home/cmh/Pi4_EdgeAI/runs/model_runtime_v4_20261029`.

- Giữ nguyên camera profile hiện hành tại
  `/home/cmh/Pi4_EdgeAI/runs/camera_profile.json`.
- Giữ giao thức UART FIFO hiện hành với ESP32.
- Chỉ `PASS` và `DEFECT` được gửi thành kết quả phân loại.
- `REVIEW` của AI được đổi thành `ERROR` để dừng an toàn, tuyệt đối không tự
  coi là `PASS`.
- Dashboard chỉ được mở qua SSH tunnel trên `127.0.0.1:8768` trong lần thử.
- Mục `Kết quả gần đây` cho phép chọn lượt chạy theo phiên ESP32, xem toàn bộ
  kết quả của phiên và tải CSV/JSON. Dữ liệu nguồn vẫn là audit JSON/ảnh được
  ghi bất đồng bộ sau khi đã gửi kết quả; file tổng hợp được giữ trong
  `captures/exports/`, không chèn I/O vào đường CAPTURE-to-RESULT.

Không chạy riêng file này trước khi hoàn thành `PREPARE_ON_PI.sh` ở thư mục
gói bàn giao.
