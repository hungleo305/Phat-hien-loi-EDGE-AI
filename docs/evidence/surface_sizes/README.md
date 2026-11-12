# Hồ sơ [5b] — So sánh kích thước đầu vào mô hình bề mặt (`960`, `832`, `768 px`)

Thư mục này lưu trữ dữ liệu thực nghiệm khảo sát ảnh hưởng của việc giảm kích thước đầu vào mô hình phát hiện lỗi bề mặt (`surface_finetuned`) trên **Raspberry Pi 4** (trình bày tại mục `3.2.3`, `Bảng 3.4` trong báo cáo).

---

## 1. Điều kiện thực nghiệm

- **Ngày thực hiện**: `04/11/2026`.
- **Cấu hình thử nghiệm**: Giữ nguyên mô hình toàn hộp `640×640` và bộ kiểm định tem; lần lượt thay đổi kích thước đầu vào (`imgsz`) của mô hình bề mặt ở 3 mức: **`960×960`**, **`832×832`** và **`768×768` pixel** trên cùng bộ **466 ảnh**.

---

## 2. Bảng tổng hợp kết quả (`Bảng 3.4`)

| Kích thước bề mặt (`px`) | Số quyết định khớp nhãn | Số ảnh lỗi bị bỏ lọt (`DEFECT -> PASS`) | Số ảnh đạt bị loại nhầm (`PASS -> DEFECT`) | Thời gian AI trung bình (`ms/ảnh`) |
|---|---:|---:|---:|---:|
| **`960 × 960` (Được chọn)** | **466 / 466** | **0** | **0** | **1097,6** |
| `832 × 832` | 414 / 466 | 40 | 12 | 1124,7 |
| `768 × 768` | 421 / 466 | 40 | 5 | 1378,1 |

*Kết luận kỹ thuật*: Khi hạ độ phân giải đầu vào xuống `832` hoặc `768 px`, các vết rách/xước mảnh trên vỏ hộp bị mờ đi khiến mô hình bỏ lọt tới `40` ảnh lỗi, đồng thời làm phát sinh thêm các lượt gọi kiểm tra lại khiến thời gian xử lý trung bình không giảm mà còn tăng lên. Vì vậy, hệ thống giữ nguyên kích thước **`960 × 960` pixel** cho mô hình bề mặt.

---

## 3. Danh mục tệp dữ liệu

- [`rows.csv`](rows.csv): Gồm `1398` dòng dữ liệu (`466 ảnh × 3 cấu hình kích thước`), ghi chi tiết tên ảnh, nhãn đối chiếu, kết luận, lý do và thời gian xử lý từng bước (`ms`).
