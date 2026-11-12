# Phân hệ 01 — Huấn luyện và đánh giá mô hình YOLOv8n

Thư mục này chứa kịch bản huấn luyện, cấu hình dữ liệu và công cụ đánh giá chỉ số cho hai mô hình phát hiện đối tượng **YOLOv8n** sử dụng trong hệ thống.

---

## 1. Vai trò của hai mô hình trong hệ thống

Hệ thống tách bài toán phát hiện bằng học sâu thành hai mô hình YOLOv8n bổ trợ cho nhau (kết hợp cùng bộ kiểm định tem bằng thị giác máy tính cổ điển ở phân hệ `03_Inference_Pi`):

| Mô hình | Kích thước đầu vào | Nhãn phát hiện | Vai trò trong pipeline kiểm định |
|---|---|---|---|
| **Mô hình toàn hộp (`whole_balanced`)** | `640 × 640` | `PASS`, `DEFECT` | Định vị vùng hộp carton trên khung hình và phát hiện sớm các hộp bị biến dạng, móp méo hoặc rách vỡ cấu trúc lớn (cổng `G1`, ngưỡng `0,70`). |
| **Mô hình bề mặt (`surface_finetuned`)** | `960 × 960` | `visible_defect` | Tập trung tìm các vết rách, xước, thủng cục bộ kích thước nhỏ trên bề mặt hộp ở độ phân giải cao (cổng `G2`, ngưỡng `0,05`, tỷ lệ diện tích khung lỗi so với hộp `≤ 0,20`). |

Hai tệp trọng số PyTorch sau huấn luyện được lưu tập trung tại [`../03_Inference_Pi/runtime/models/whole_balanced.pt`](../03_Inference_Pi/runtime/models/whole_balanced.pt) và [`surface_finetuned.pt`](../03_Inference_Pi/runtime/models/surface_finetuned.pt).

---

## 2. Danh mục tệp trong thư mục

| Tên tệp | Chức năng |
|---|---|
| [`train.py`](train.py) | Kịch bản huấn luyện chính (mặc định huấn luyện mô hình toàn hộp `640×640`, hoặc truyền `--model surface` cho mô hình bề mặt `960×960`). |
| [`train_surface.py`](train_surface.py) | Điểm gọi nhanh để huấn luyện mô hình bề mặt (`960×960`), sử dụng chung nhân huấn luyện trong `train.py`. |
| [`evaluate.py`](evaluate.py) | Kịch bản đo các chỉ số `Precision`, `Recall`, `mAP@50` và `mAP@50–95` của từng mô hình trên tập kiểm thử/xác thực. |
| [`data.yaml`](data.yaml) | Cấu hình đường dẫn và danh sách lớp của bộ dữ liệu toàn hộp. |
| [`results.png`](results.png), [`confusion_matrix_normalized.png`](confusion_matrix_normalized.png) | Biểu đồ quá trình hội tụ hàm mất mát, `mAP` và ma trận nhầm lẫn chuẩn hóa từ quá trình huấn luyện. |

---

## 3. Dữ liệu huấn luyện và kết quả đạt được

- **Bộ dữ liệu toàn hộp (V4 — 295 ảnh gốc)**: Chia theo nhóm hộp vật lý gồm **205 ảnh huấn luyện** (`50 PASS`, `155 DEFECT`), **40 ảnh xác thực** (`10 PASS`, `30 DEFECT`) và **50 ảnh kiểm thử** (`20 PASS`, `30 DEFECT`). Trong tập huấn luyện, 50 ảnh `PASS` được nhân bản 3 lần (`150` lượt `PASS` so với `155` lượt `DEFECT`, tổng `305` lượt ảnh/epoch) để cân bằng lớp.
- **Bộ dữ liệu bề mặt kết hợp (559 ảnh)**: Hợp nhất **354 ảnh** từ giai đoạn phát triển trước với **205 ảnh huấn luyện V4** (gồm `373` ảnh có nhãn `visible_defect` và `186` ảnh nền không có lỗi bề mặt), đánh giá trên **40 ảnh xác thực V4** độc lập.

| Mô hình | Đầu vào | Epochs | Batch | Precision | Recall | mAP@50 | mAP@50–95 | Tập đánh giá |
|---|---|---:|---:|---:|---:|---:|---:|---|
| **Toàn hộp (`whole_balanced`)** | `640 × 640` | 80 | 8 | `0,650` | `0,786` | `0,726` | `0,560` | Kiểm thử V4 (50 ảnh) |
| **Bề mặt (`surface_finetuned`)** | `960 × 960` | 60 | 4 | `0,398` | `0,470` | `0,391` | `0,161` | Xác thực V4 (40 ảnh) |

Chi tiết kiểm kê dữ liệu và tham số huấn luyện được lưu tại [`../docs/evidence/training_data/`](../docs/evidence/training_data/README.md).

---

## 4. Hướng dẫn chạy huấn luyện và đánh giá

Chạy từ thư mục gốc của kho mã nguồn (yêu cầu môi trường Python có `torch` và `ultralytics`; truyền đường dẫn `--output` mới để không ghi đè kết quả cũ):

```powershell
# Huấn luyện lại mô hình toàn hộp (640x640) và mô hình bề mặt (960x960)
python 01_Training/train.py --output F:/DATN/Cong_cu_phat_trien/outputs/train_whole_run
python 01_Training/train_surface.py --output F:/DATN/Cong_cu_phat_trien/outputs/train_surface_run

# Đánh giá chỉ số Precision, Recall, mAP của hai mô hình
python 01_Training/evaluate.py --model whole --output F:/DATN/Cong_cu_phat_trien/outputs/eval_whole_run
python 01_Training/evaluate.py --model surface --output F:/DATN/Cong_cu_phat_trien/outputs/eval_surface_run
```

Nếu chạy trên máy tính khác, truyền thêm tham số `--data <duong_dan_data.yaml>` và `--weights <duong_dan_checkpoint.pt>` trỏ tới thư mục dữ liệu tương ứng.
