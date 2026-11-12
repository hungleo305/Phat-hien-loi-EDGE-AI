# Hồ sơ [6] — Đối chiếu thời gian xử lý giữa Raspberry Pi 4 và Laptop Acer

Thư mục này lưu trữ dữ liệu so sánh tốc độ thực thi thuật toán kiểm định giữa máy tính nhúng **Raspberry Pi 4** và máy tính cá nhân **Laptop Acer** trên cùng một bộ ảnh đầu vào (trình bày tại mục `3.5.2`, `Bảng 3.9` và `Phụ lục B`, `Bảng B.1` trong báo cáo).

---

## 1. Điều kiện thực nghiệm

- **Ngày thực hiện**: `10/11/2026`.
- **Phần cứng đối chiếu**:
  - **Raspberry Pi 4 Model B**: Vi xử lý ARM Cortex-A72 (chạy CPU 4 luồng).
  - **Laptop Acer**: Vi xử lý Intel Core i5-11400H (chạy CPU 6 luồng, không sử dụng GPU rời).
- **Phương pháp đo**: Hai máy chạy cùng mã nguồn pipeline, cùng trọng số NCNN FP32 và mẫu tem tham chiếu trên **11 tệp ảnh camera** (`6` mẫu hộp lỗi `01–06` và `5` mẫu hộp đạt `07–11`, trong đó mẫu `09–11` có cùng nội dung ảnh hộp đạt). Sau bước khởi động làm nóng mô hình (`warmup`), mỗi mẫu ảnh được chạy lặp lại **3 lần trên mỗi máy** (tổng cộng `33` lần gọi hàm kiểm định trên mỗi nền tảng).

---

## 2. Kết quả tổng hợp (`Bảng 3.9`) và chi tiết từng mẫu (`Bảng B.1`)

### Tổng hợp trên 11 mẫu ảnh (33 lượt đo/máy):

| Chỉ tiêu so sánh | Raspberry Pi 4 | Laptop Acer | Tỷ số (Pi 4 / Acer) |
|---|---:|---:|---:|
| **Quyết định khớp nhãn đối chiếu** | **11 / 11** (33/33 lượt) | **11 / 11** (33/33 lượt) | Đồng nhất 100% |
| **Thời gian trung bình (`s/ảnh`)** | **0,984** (`984,4 ms`) | **0,158** (`158,2 ms`) | **6,22 ×** |
| **Thời gian trung vị (`s/ảnh`)** | **0,652** (`652,4 ms`) | **0,120** (`119,6 ms`) | 5,45 × |
| **Phân vị thứ 95 — p95 (`s/ảnh`)** | **1,756** (`1756,3 ms`) | **0,299** (`299,3 ms`) | 5,87 × |

### Thời gian xử lý trung bình từng mẫu ảnh (`paired_by_image.csv` — `Bảng B.1`):

| Mã mẫu | Phân loại | Lý do kết luận của thuật toán | Raspberry Pi 4 (`ms`) | Laptop Acer (`ms`) |
|---|---|---|---|---|
| **Mẫu 01** | Hộp lỗi (`DEFECT`) | Sai trường QC/năm trên tem (`QC/year mismatch`) | `653,4` | `118,8` |
| **Mẫu 02** | Hộp lỗi (`DEFECT`) | Lỗi toàn hộp (`whole-box model`) — kết luận sớm Bước 1 | `417,1` | `59,3` |
| **Mẫu 03** | Hộp lỗi (`DEFECT`) | Lỗi toàn hộp (`whole-box model`) — kết luận sớm Bước 1 | `411,0` | `53,6` |
| **Mẫu 04** | Hộp lỗi (`DEFECT`) | Lỗi toàn hộp (`whole-box model`) — kết luận sớm Bước 1 | `413,1` | `53,2` |
| **Mẫu 05** | Hộp lỗi (`DEFECT`) | Lỗi toàn hộp (`whole-box model`) — kết luận sớm Bước 1 | `409,8` | `53,2` |
| **Mẫu 06** | Hộp lỗi (`DEFECT`) | Lỗi toàn hộp (`whole-box model`) — kết luận sớm Bước 1 | `415,7` | `57,5` |
| **Mẫu 07** | Hộp đạt (`PASS`) | Đạt tất cả bước kiểm tra (`all active checks passed`) | `1525,7` | `245,9` |
| **Mẫu 08** | Hộp đạt (`PASS`) | Đạt tất cả bước kiểm tra (`all active checks passed`) | `1538,1` | `252,9` |
| **Mẫu 09** | Hộp đạt (`PASS`) | Đạt tất cả bước kiểm tra (`all active checks passed`) | `1750,7` | `297,9` |
| **Mẫu 10** | Hộp đạt (`PASS`) | Đạt tất cả bước kiểm tra (`all active checks passed`) | `1748,9` | `301,0` |
| **Mẫu 11** | Hộp đạt (`PASS`) | Đạt tất cả bước kiểm tra (`all active checks passed`) | `1545,0` | `246,8` |

---

## 3. Danh mục tệp dữ liệu

- [`paired_by_image.csv`](paired_by_image.csv): Kết quả quyết định và thời gian trung bình (`ms`) của từng mẫu ảnh từ `01` đến `11`.
- [`paired_summary.json`](paired_summary.json): Thông tin môi trường phần cứng, mã băm gói runtime và số liệu đo chi tiết của cả 33 lượt chạy trên mỗi máy.
- [`thoi_gian_pi_acer.png`](thoi_gian_pi_acer.png): Biểu đồ trực quan so sánh thời gian xử lý theo nhóm mẫu ảnh (`Hình 3.15` trong báo cáo).
