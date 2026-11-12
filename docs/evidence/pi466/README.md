# Hồ sơ [3] — Đánh giá hồi quy toàn bộ pipeline trên 466 ảnh tại Raspberry Pi 4

Thư mục này lưu trữ kết quả chạy kiểm tra toàn bộ thuật toán kiểm định ảnh (**YOLOv8n NCNN FP32 + ORB/Homography/NCC + Hậu kiểm**) trên **466 ảnh** tại **Raspberry Pi 4** (trình bày tại mục `3.5.1`, `Bảng 3.8` trong báo cáo).

---

## 1. Thành phần bộ 466 ảnh và kết quả nhận diện (`Bảng 3.8`)

Ngày thực hiện phép đo: `01/11/2026`. Chương trình chạy trực tiếp hàm kiểm định NCNN FP32 trên Raspberry Pi 4 với 466 ảnh đã lưu từ 3 nhóm nguồn:

| Nhóm nguồn ảnh | Số ảnh `PASS` theo nhãn đối chiếu | Số ảnh `DEFECT` theo nhãn đối chiếu | Tổng số ảnh | Số quyết định đúng |
|---|---:|---:|---:|---:|
| `original_245` — Bộ ảnh hộp ban đầu | 80 | 165 | 245 | **245 / 245** |
| `pi_regression_80` — Bộ ảnh kiểm thử trên Pi | 20 | 60 | 80 | **80 / 80** |
| `camera_sessions_141` — Ảnh thu từ các phiên chụp buồng camera | 89 | 52 | 141 | **141 / 141** |
| **Tổng cộng** | **189** | **277** | **466** | **466 / 466 (100%)** |

### Thống kê thời gian xử lý AI trên Raspberry Pi 4:
- **Thời gian trung bình (`mean`)**: **`889,1 ms / ảnh`**
- **Thời gian trung vị (`median`)**: **`720,0 ms / ảnh`**
- **Thời gian lớn nhất (`max`)**: **`1603,2 ms / ảnh`**

*(Các mẫu lỗi nặng ở Bước 1 hoặc lỗi tem ở Bước 2 kết thúc sớm nên tốn ít thời gian hơn; các mẫu hộp đạt đi qua đủ cả 3 bước gồm cả mô hình bề mặt `960×960`).*

---

## 2. Danh mục tệp dữ liệu

- [`summary.json`](summary.json): Thông số tổng hợp toàn bộ 466 ảnh và kết quả thống kê chi tiết theo từng nhóm hộp con.
- [`results.csv`](results.csv): Bảng kết quả từng ảnh trong 466 ảnh (nhóm nguồn, tên tệp, mã băm SHA-256 của ảnh, nhãn đối chiếu `truth`, quyết định `decision`, cờ đối chiếu `correct`, lý do `reason` và thời gian xử lý `ai_ms`).
