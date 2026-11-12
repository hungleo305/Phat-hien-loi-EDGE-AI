# Hồ sơ [5a] — So sánh trọng số NCNN FP32 và NCNN FP16 trên Raspberry Pi 4

Thư mục này lưu trữ dữ liệu thực nghiệm đối chiếu giữa hai định dạng trọng số **NCNN FP32** và **NCNN FP16** trên cùng một máy **Raspberry Pi 4** (trình bày tại mục `3.2.3`, `Bảng 3.4` trong báo cáo).

---

## 1. Điều kiện thực nghiệm

- **Ngày thực hiện**: `04/11/2026`.
- ** Tập dữ liệu thử nghiệm**: Cùng bộ **466 ảnh** lưu trữ (`189 PASS`, `277 DEFECT`), chạy qua toàn bộ pipeline kiểm định 3 bước.
- **Điều kiện đo**: Cả hai cấu hình chạy tuần tự trên Raspberry Pi 4 trong cùng điều kiện dịch vụ trạm đang hoạt động; thời gian đo là thời gian xử lý của hàm kiểm định ảnh (không tính thời gian thu camera và cơ khí).

---

## 2. Bảng tổng hợp kết quả (`summary.json`)

| Chỉ tiêu so sánh | NCNN FP32 (Đang dùng) | NCNN FP16 (Ứng viên thử nghiệm) |
|---|---:|---:|
| **Số quyết định khớp nhãn đối chiếu** | **466 / 466** | **466 / 466** |
| **Thời gian xử lý trung bình (`ms/ảnh`)** | **1071,8** | 1096,0 |
| **Thời gian xử lý trung vị (`ms/ảnh`)** | **802,9** | 811,8 |
| **Phân vị thứ 95 — p95 (`ms/ảnh`)** | **1695,8** | 1732,7 |

*Kết luận kỹ thuật*: Trên vi xử lý ARM Cortex-A72 của Raspberry Pi 4, việc xuất trọng số sang `FP16` giúp giảm kích thước tệp lưu trữ nhưng không rút ngắn thời gian suy luận thực tế so với `FP32` (`1096,0 ms` so với `1071,8 ms`). Do đó, hệ thống giữ bản **NCNN FP32** cho vận hành chính thức.

---

## 3. Danh mục tệp dữ liệu

- [`summary.json`](summary.json): Số liệu thống kê tổng hợp của phép so sánh FP32 và FP16.
- [`comparison.csv`](comparison.csv): Bảng đối chiếu chi tiết từng ảnh trong 466 ảnh (quyết định, lý do và thời gian xử lý ở cả hai chế độ FP32 và FP16).
