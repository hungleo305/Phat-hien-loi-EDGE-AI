# Gói Runtime AI chuẩn (`03_Inference_Pi/runtime`)

Thư mục này là gói phần mềm kiểm định ảnh chuẩn đang vận hành thực tế trên Raspberry Pi 4 (`/home/cmh/Pi4_EdgeAI/current/runtime`). Toàn bộ tệp trong gói được bảo vệ bằng mã băm SHA-256 khai báo trong [`manifest.json`](manifest.json).

---

## 1. Cấu trúc tệp trong gói `runtime/`

| Đường dẫn | Chức năng chi tiết |
|---|---|
| [`config/app.json`](config/app.json) | Khai báo kích thước đầu vào (`640` / `960`), ngưỡng quyết định (`0,70` / `0,05`), tỷ lệ diện tích tối đa (`0,20`), số luồng CPU và quy tắc chuyển `REVIEW -> ERROR`. |
| [`src/current_pipeline.py`](src/current_pipeline.py) | Pipeline kiểm định chính 3 bước có kết luận sớm (Toàn hộp -> Kiểm định tem -> Bề mặt) và loại trừ vùng logo bằng Homography. |
| [`src/base_pipeline.py`](src/base_pipeline.py) | Lớp cơ sở quản lý nạp mô hình (`NCNN` hoặc `PyTorch`), khởi động làm nóng (`warmup`) và vẽ khung kết quả (`annotate`). |
| [`src/label_verifier.py`](src/label_verifier.py) | Bộ định vị và xác thực tem bằng đặc trưng ORB (`1800` điểm), biến đổi phối cảnh Homography (`USAC_MAGSAC`) và kiểm tra 6 vùng nội dung. |
| [`src/label_integrity.py`](src/label_integrity.py) | Bộ kiểm tra trường cố định (`QC PASSED`, năm `2026`), phát hiện vết bẩn/vẽ thêm và vết rách lộ nền giấy carton. |
| [`src/guard_logic.py`](src/guard_logic.py) | Các bộ lọc hậu kiểm theo đặc trưng vùng sáng của tem, độ lõm biên dạng hộp và lọc nhiễu viền tem. |
| [`src/pi_camera.py`](src/pi_camera.py), [`src/camera_controls.py`](src/camera_controls.py) | Giao tiếp thu ảnh từ camera USB UVC và đọc/ghi thông số điều khiển V4L2 trên Linux. |
| [`models/`](models/) | Chứa 2 thư mục mô hình NCNN FP32 (`whole_balanced_ncnn_model/`, `surface_finetuned_ncnn_model/`) và 2 tệp trọng số PyTorch gốc (`whole_balanced.pt`, `surface_finetuned.pt`). |
| [`assets/`](assets/) | Ảnh mẫu tem hợp lệ (`approved_label.png`) và 3 mẫu đối chiếu trường lỗi (`tem_QC_FAILED_2026_cropped.png`, `tem_QC_FAILED_2025_cropped.png`, `tem_QC_PASSED_2025_cropped.png`). |
| [`samples/`](samples/), [`self_check.py`](self_check.py) | Bộ 5 ảnh kiểm tra hồi quy nhanh (`pass.jpg`, `qc_failed.jpg`, `added_marks.jpg`, `physical_defect.jpg`, `review.jpg`) và kịch bản tự kiểm tra. |
| [`integrity.py`](integrity.py), [`manifest.json`](manifest.json) | Mô-đun kiểm tra độc lập mã băm SHA-256 của toàn bộ 31 tệp trong gói trước khi nạp thư viện AI. |

---

## 2. Chạy kiểm tra nhanh gói `runtime/`

```bash
python 03_Inference_Pi/runtime/self_check.py --backend ncnn
```

*Lưu ý về ảnh mẫu `samples/review.jpg`*: Tệp giữ tên lịch sử từ giai đoạn rà soát lỗi viền, nhưng có cùng nội dung (trùng mã băm SHA-256) với mẫu hộp đạt `PASS13_QC_PASSED_2026_01.jpg` và được dùng để xác nhận nhánh lọc cảnh báo giả ở viền tem trả về đúng kết luận `PASS`.
