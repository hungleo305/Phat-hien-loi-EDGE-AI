# Kiến trúc mã nguồn và luồng dữ liệu

Tài liệu này giải thích cách tổ chức mã nguồn trong kho Git, luồng phối hợp giữa các phân hệ khi vận hành và cơ chế kiểm soát tính toàn vẹn của gói phần mềm.

---

## 1. Luồng hoạt động tổng thể của hệ thống

```text
[Cảm biến chụp (GPIO18)]
       │ (Phát hiện hộp -> Dừng băng tải sau 250 ms ổn định)
       ▼
[ESP32 Firmware (FIFO + FSM)] ──(UART2: CAPTURE <session> <id>)──► [05_Dashboard/station (run_station.py)]
       ▲                                                                     │
       │ (UART2: CAPTURED -> Băng tải có thể chạy lại)                       ├── 1. Thu ảnh từ Camera USB (V4L2/UVC)
       │                                                                     ├── 2. Gọi 03_Inference_Pi/runtime:
       │                                                                     │      • Bước 1: YOLOv8n toàn hộp (640×640)
       │ (UART2: RESULT <session> <id> PASS|DEFECT|ERROR)                    │      • Bước 2: ORB + Homography + NCC (Tem)
       └─────────────────────────────────────────────────────────────────────┤      • Bước 3: YOLOv8n bề mặt (960×960)
                                                                             └── 3. Cập nhật Web Dashboard (HTTP/MJPEG)
[Cảm biến cửa gạt (GPIO19)]
       │
       ▼
[ESP32 đọc kết quả hộp đầu hàng đợi FIFO]
  ├── PASS   -> Cho hộp đi thẳng qua cửa gạt
  ├── DEFECT -> Kích hoạt Servo SG90 (GPIO13) gạt hộp sang nhánh loại (khi ở chế độ SORT)
  └── ERROR  -> Dừng băng tải an toàn, báo FAULT chờ người vận hành xử lý
```

---

## 2. Nguyên tắc "Một nguồn duy nhất" (Single Source of Truth)

Để tránh sai lệch giữa bản chạy thực tế và bản lưu trữ, mỗi thành phần chỉ đặt tại một vị trí duy nhất trong kho:

| Thành phần | Đường dẫn chuẩn duy nhất | Ghi chú phụ thuộc |
|---|---|---|
| **Runtime AI & Trọng số mô hình** | [`03_Inference_Pi/runtime/`](../03_Inference_Pi/runtime/README.md) | Chứa toàn bộ mã kiểm định (`src/`), cấu hình ngưỡng (`config/app.json`), mẫu tem (`assets/`), 2 mô hình NCNN FP32 và 2 checkpoint PyTorch `.pt` gốc (`models/`). Các phân hệ khác không giữ bản sao mô hình. |
| **Cấu hình Camera Pi** | [`03_Inference_Pi/camera_profile.json`](../03_Inference_Pi/camera_profile.json) | Thông số UVC/V4L2 trên Raspberry Pi 4 (`exposure_time_absolute = 1100`, `gain = 1`, `sharpness = 135`...). |
| **Trạm điều phối & Web Dashboard** | [`05_Dashboard/station/`](../05_Dashboard/station/README.md) | Điều phối camera, tiến trình AI, giao thức UART2 và phục vụ giao diện web (`dashboard.html`, `dashboard.css`, `dashboard.js`). |
| **Firmware vi điều khiển ESP32** | [`04_ESP32_Firmware/`](../04_ESP32_Firmware/README.md) | Mã nguồn C duy nhất cho ESP32-WROOM-32 (ESP-IDF 5.3.5). |
| **Huấn luyện & Tối ưu hóa mô hình** | [`01_Training/`](../01_Training/README.md), [`02_Optimization/`](../02_Optimization/README.md) | Các kịch bản độc lập dùng trên máy tính khi cần huấn luyện lại hoặc xuất thử nghiệm ứng viên NCNN FP16 mới; không tham gia vào vòng lặp điều khiển trên Pi. |
| **Lưu đồ & Hồ sơ thực nghiệm** | [`docs/diagrams/`](diagrams/README.md), [`docs/evidence/`](evidence/README.md) | Toàn bộ sơ đồ kỹ thuật và dữ liệu thực nghiệm gốc phục vụ đối chiếu với báo cáo đồ án. |

---

## 3. Phân tách mã nguồn trong Git và dữ liệu ngoài Git

- **Trong kho Git (`DATN_Source/`)**: Lưu mã nguồn, trọng số mô hình đang vận hành, mẫu tem chuẩn, cấu hình mặc định, 5 ảnh tự kiểm tra (`samples/`), lưu đồ hệ thống và các tệp số liệu thực nghiệm (`CSV`, `JSON`, `YAML`).
- **Ngoài kho Git**:
  - Bộ ảnh gốc dung lượng lớn dùng để huấn luyện và bộ 466 ảnh chạy hồi quy được lưu trong thư mục dữ liệu của máy phát triển (`F:/DATN/Du_lieu_goc/`).
  - Các khóa kết nối SSH, thư mục biên dịch (`build/`), bộ nhớ đệm (`__pycache__/`) và nhật ký phiên chạy phát sinh hàng ngày (`runs/`, `captures/`) được loại trừ qua `.gitignore`.

---

## 4. Cơ chế bảo vệ tính toàn vẹn (Manifest & SHA-256)

Hệ thống sử dụng ba lớp kiểm tra mã băm SHA-256 để đảm bảo không có tệp mô hình, cấu hình hay số liệu nào bị hỏng hoặc thay đổi ngoài ý muốn:

1. [`03_Inference_Pi/runtime/manifest.json`](../03_Inference_Pi/runtime/manifest.json): Ghi mã băm SHA-256 của toàn bộ 31 tệp trong gói runtime AI (mô hình, mẫu tem, mã nguồn, cấu hình). Hàm `integrity.verify()` kiểm tra danh sách này trước khi nạp mô hình.
2. [`05_Dashboard/station/manifest.json`](../05_Dashboard/station/manifest.json): Ghi mã băm SHA-256 của toàn bộ 9 tệp thuộc gói điều phối trạm và giao diện web.
3. [`docs/evidence/SHA256SUMS`](evidence/SHA256SUMS): Ghi mã băm SHA-256 của toàn bộ 29 tệp minh chứng thực nghiệm được trích dẫn trong báo cáo đồ án.

Chạy lệnh `python tools/verify_repository.py` từ gốc kho sẽ tự động xác minh đồng thời cả 3 danh mục mã băm trên, kiểm tra cú pháp toàn bộ tệp Python và rà soát mọi liên kết tài liệu cục bộ.
