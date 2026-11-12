# Phân hệ 03 — Suy luận Edge AI và kiểm định tem trên Raspberry Pi 4

Thư mục này chứa gói phần mềm suy luận chuẩn (**`runtime/`**) và hồ sơ cấu hình camera (**`camera_profile.json`**) chạy trực tiếp trên **Raspberry Pi 4**.

---

## 1. Cấu trúc phân hệ

| Thành phần | Vai trò |
|---|---|
| [`runtime/`](runtime/README.md) | Gói AI chuẩn duy nhất của kho mã: chứa mã nguồn pipeline 3 bước (`src/`), cấu hình ngưỡng (`config/app.json`), 2 mô hình NCNN FP32 & 2 checkpoint PyTorch (`models/`), mẫu tem chuẩn (`assets/`), 5 ảnh tự kiểm tra (`samples/`) và cơ chế xác thực `manifest.json`. |
| [`camera_profile.json`](camera_profile.json) | Hồ sơ thông số camera USB UVC/V4L2 trên Raspberry Pi 4 (`exposure_time_absolute = 1100`, `gain = 1`, `gamma = 20`, `sharpness = 135`, `white_balance_temperature = 5000`). |
| [`run_station.py`](run_station.py) | Kịch bản khởi chạy trạm kiểm định trên Pi, tự động truyền đúng đường dẫn `runtime/` và `camera_profile.json` vào bộ điều phối tại `05_Dashboard/station/run_station.py`. |

---

## 2. Luồng thuật toán kiểm định ảnh và các cổng quyết định

Quy trình kiểm định một khung hình trong [`runtime/src/current_pipeline.py`](runtime/src/current_pipeline.py) được thiết kế theo cơ chế **Một lượt và Kết luận sớm (Single-Pass & Early-Exit)** nhằm giảm thời gian tính toán trên Raspberry Pi 4 (xem lưu đồ tại [`../docs/diagrams/pipeline_ai_chi_tiet.png`](../docs/diagrams/pipeline_ai_chi_tiet.png) và [`../docs/diagrams/kiem_dinh_tem_chi_tiet.png`](../docs/diagrams/kiem_dinh_tem_chi_tiet.png)):

1. **Bước 1 — Phát hiện toàn hộp (`YOLOv8n NCNN FP32`, `640×640`)**:
   - Tìm khung bao hộp carton (`PASS` hoặc `DEFECT`).
   - **Cổng `G1` (`whole_threshold = 0,70`)**: Nếu phát hiện lớp `DEFECT` với điểm tự tin `≥ 0,70`, kết luận ngay **`DEFECT` (`whole-box model`)** và dừng sớm mà không cần chạy bước kiểm tra tem hay mô hình bề mặt.
2. **Bước 2 — Kiểm định tem nhãn (`ORB + Homography USAC_MAGSAC + NCC`)**:
   - Cắt vùng ảnh quanh hộp (mở rộng lề `30%`) để định vị tem bằng **1800 đặc trưng ORB**, lọc tỷ số Lowe `0,74` (tối thiểu `12` cặp điểm khớp) và ước lượng ma trận **Homography bằng `USAC_MAGSAC`** (yêu cầu `≥ 10` inliers, tỷ lệ inlier `≥ 0,40`, độ phủ đa giác lồi `≥ 0,18`). Nếu vùng cắt chưa đủ thông tin, hệ thống tự động thử lại trên toàn khung hình.
   - Nếu không tìm thấy cả hộp lẫn tem -> trả về **`REVIEW`** (trạm chuyển thành bản tin `ERROR` để dừng an toàn). Nếu có hộp nhưng không có tem (`NOLABEL`) -> kết luận ngay **`DEFECT` (`missing label on detected cardboard box`)**.
   - Nếu định vị được tem nhưng cạnh ngắn `< 90 px`, phần nằm trong ảnh `< 96%` hoặc độ sắc nét Laplacian `< 35` -> trả về **`REVIEW`** (`insufficient_detail`).
   - Sau khi căn chỉnh phối cảnh tem về kích thước chuẩn `320×320 px`, **Cổng `G3`** đối chiếu 6 vùng nội dung (`logo`, `school`, `project`, `inspector`, `qc`, `year`) bằng tương quan chéo chuẩn hóa (**NCC**) và mật độ cạnh Canny, đồng thời so khớp với 3 mẫu tem lỗi (`QC FAILED 2026`, `QC FAILED 2025`, `QC PASSED 2025`) và tìm vết bẩn/vẽ thêm hoặc rách tem lộ nền carton. Nếu vi phạm bất kỳ điều kiện nào -> kết luận ngay **`DEFECT`**.
3. **Bước 3 — Phát hiện lỗi bề mặt cục bộ (`YOLOv8n NCNN FP32`, `960×960`)**:
   - Chỉ chạy khi tem đã được xác nhận hợp lệ (`verified`).
   - Dùng ma trận Homography ánh xạ vùng `logo` sang ảnh gốc để **loại trừ cảnh báo giả do họa tiết quốc huy/logo trường**.
   - **Cổng `G2` (`surface_threshold = 0,05`, `surface_max_area_ratio = 0,20`)**: Nếu tồn tại khung lỗi `visible_defect` nằm trong phạm vi hộp có điểm tự tin `≥ 0,05` và diện tích `≤ 20%` diện tích hộp -> kết luận **`DEFECT` (`visible physical defect`)**; ngược lại kết luận **`PASS` (`all active checks passed`)**.
4. **Hậu kiểm hình học (`guard_logic.py`)**: Kiểm tra bổ sung độ lõm biên dạng hộp (`silhouette_concavity`) và triệt tiêu cảnh báo giả ở sát mép viền tem khi toàn hộp và bề mặt đều sạch.

---

## 3. Hướng dẫn tự kiểm tra và khởi chạy

Từ thư mục gốc của kho mã nguồn:

```bash
# 1. Chạy tự kiểm tra tính toàn vẹn SHA-256 và suy luận NCNN trên 5 ảnh mẫu chuẩn
python 03_Inference_Pi/runtime/self_check.py --backend ncnn

# 2. Khởi chạy trạm kiểm định kèm Web Dashboard (trên Raspberry Pi 4 có kết nối Camera & UART2)
python 03_Inference_Pi/run_station.py --headless --dashboard --dashboard-local-trust
```

Kết quả mong đợi khi chạy `self_check.py`: xác thực thành công `manifest.json` và trả về kết quả chính xác **5/5 ảnh mẫu** (`SELF CHECK PASSED 5/5`). Xem thêm chi tiết bên trong [`runtime/README.md`](runtime/README.md) và hồ sơ đánh giá 466 ảnh tại [`../docs/evidence/pi466/README.md`](../docs/evidence/pi466/README.md).
