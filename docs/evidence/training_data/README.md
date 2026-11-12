# Hồ sơ [1] — Dữ liệu và kết quả huấn luyện hai mô hình YOLOv8n

Thư mục này lưu trữ thông số cấu hình, thống kê phân bố dữ liệu và kết quả đánh giá của hai mô hình **YOLOv8n** (trình bày tại mục `3.2.1` và `3.2.2`, `Bảng 3.1`–`3.3` trong báo cáo).

---

## 1. Phân bố bộ dữ liệu V4 (`v4_audit.json` — 295 ảnh)

Tệp [`v4_audit.json`](v4_audit.json) ghi lại phân bố chi tiết của **295 ảnh gốc** (`1280×1280 px`), được chia tách theo nhóm hộp vật lý để tránh rò rỉ dữ liệu giữa các tập:

| Tập dữ liệu | Số ảnh hộp đạt (`PASS`) | Số ảnh hộp lỗi (`DEFECT`) | Tổng số ảnh | Số vùng lỗi bề mặt gán nhãn (`class_2`) |
|---|---:|---:|---:|---:|
| **Huấn luyện (`train`)** | 50 | 155 | **205** | 147 |
| **Xác thực (`valid`)** | 10 | 30 | **40** | 100 |
| **Kiểm thử (`test`)** | 20 | 30 | **50** | 41 |
| **Tổng cộng** | **80** | **215** | **295** | **288** |

*Ghi chú*:
- Một ảnh hộp lỗi có thể chứa nhiều vùng rách/xước локаl (`class_2`), nên tổng số vùng gán nhãn `class_2` (`288` vùng) là số khung bao lỗi cục bộ, không phải số ảnh.
- Khi huấn luyện **mô hình toàn hộp (`whole_balanced`)** trên 205 ảnh nguồn của tập `train`, 50 ảnh `PASS` được lặp lại 3 lần (`150` lượt `PASS` so với `155` lượt `DEFECT`, tổng cộng `305` lượt ảnh trong một epoch) để cân bằng tỷ lệ giữa hai lớp.

---

## 2. Phân bố bộ dữ liệu bề mặt kết hợp (`surface_combined_audit.json` — 559 ảnh)

Để tăng số lượng mẫu vết rách, xước và hư hại cục bộ cho **mô hình bề mặt (`surface_finetuned`)**, hệ thống kết hợp 354 ảnh từ giai đoạn phát triển trước với 205 ảnh huấn luyện V4 (xem [`surface_combined_audit.json`](surface_combined_audit.json)):

| Nguồn dữ liệu | Tổng số ảnh | Ảnh có vùng lỗi bề mặt (`visible_defect`) | Ảnh không có vùng lỗi bề mặt |
|---|---:|---:|---:|
| **Bộ dữ liệu giai đoạn trước** | 354 | 263 | 91 |
| **Tập huấn luyện V4** | 205 | 110 | 95 |
| **Tổng tập huấn luyện bề mặt** | **559** | **373** | **186** |

*Ghi chú*: Tập đánh giá của mô hình bề mặt là **40 ảnh xác thực V4 (`valid`)**, hoàn toàn tách biệt khỏi 559 ảnh huấn luyện trên.

---

## 3. Kết quả đánh giá hai mô hình YOLOv8n (`Bảng 3.3`)

| Mô hình | Kích thước đầu vào | Precision | Recall | mAP@50 | mAP@50–95 | Tập đo chỉ số | Tệp số liệu gốc |
|---|---|---:|---:|---:|---:|---|---|
| **Toàn hộp (`whole_balanced`)** | `640 × 640` | `0,650` | `0,786` | `0,726` | `0,560` | Kiểm thử V4 (`50` ảnh) | [`whole_metrics.json`](whole_metrics.json), [`whole_args.yaml`](whole_args.yaml) |
| **Bề mặt (`surface_finetuned`)** | `960 × 960` | `0,398` | `0,470` | `0,391` | `0,161` | Xác thực V4 (`40` ảnh) | [`surface_metrics.json`](surface_metrics.json), [`surface_args.yaml`](surface_args.yaml) |

### Đối chiếu mã băm SHA-256 của 2 checkpoint PyTorch chuẩn trong `03_Inference_Pi/runtime/models/`:
- `whole_balanced.pt`: `cee48c449020ad81f3e1bc952bf1dacd95c4d067bec1bf42fb3ca08e58c63848`
- `surface_finetuned.pt`: `4539b799ed3990c6b5554b847cdfd66be7f4fb7732ceae386a88a7f4b45ec447`
