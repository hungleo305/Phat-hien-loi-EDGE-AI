# So sánh kích thước đầu vào mô hình bề mặt

Ngày đo: 04/11/2026. Cùng Pi, chương trình, mô hình FP32 và 466 ảnh; lần lượt dùng kích thước bề mặt 960, 832, 768 pixel. Các phần khác giữ theo cấu hình của phép thử.

| Kích thước | Quyết định khớp nhãn bộ ảnh | Bỏ lọt DEFECT | Loại nhầm PASS | AI trung bình (ms) |
|---|---:|---:|---:|---:|
| 960 | 466/466 | 0 | 0 | 1097,6 |
| 832 | 414/466 | 40 | 12 | 1124,7 |
| 768 | 421/466 | 40 | 5 | 1378,1 |

Giữ đầu vào 960 vì hai cấu hình giảm kích thước làm mất kết quả và không giảm thời gian trung bình trong phép thử.

[rows.csv](rows.csv) có 1398 hàng dữ liệu (466 ảnh × 3 kích thước), chứa kích thước, tên ảnh, nhãn, quyết định, lý do và thời gian từng phần (ms). `roi_calls`/`full_calls` là số lần gọi bộ kiểm định tem trên vùng ảnh/toàn ảnh. p95 và các thống kê có thể tính lại từ các cột thời gian. Các cấu hình chạy tuần tự, nên phép đo chưa loại hết ảnh hưởng của tải và nhiệt độ.
