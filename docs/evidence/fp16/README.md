# So sánh FP32 và FP16 trên cùng Pi

Ngày đo: 04/11/2026. Hai cấu hình dùng cùng chương trình và cùng 466 ảnh đã lưu. FP32 chạy trước, FP16 chạy sau; dịch vụ trạm vẫn hoạt động. Thời gian là thời gian kiểm định ảnh, không gồm camera và cơ khí.

| Chỉ tiêu | FP32 | FP16 |
|---|---:|---:|
| Quyết định khớp nhãn bộ ảnh | 466/466 | 466/466 |
| Trung bình (ms) | 1071,8 | 1096,0 |
| Trung vị (ms) | 802,9 | 811,8 |
| p95 (ms) | 1695,8 | 1732,7 |

Cả 466 quyết định giống nhau, nhưng FP16 không nhanh hơn trong phép đo này. Hệ thống giữ FP32. Không so sánh trực tiếp thời gian này với lần chạy 01/11 để suy ra hiệu quả một thay đổi, vì là các lượt đo khác nhau.

- [comparison.csv](comparison.csv): thời gian và quyết định từng ảnh ở cả hai cấu hình.
- [summary.json](summary.json): kết quả tổng hợp gốc.

Bộ ảnh đã tham gia phát triển, nên đây không phải đánh giá độ chính xác trên hộp mới. Khác biệt nhiệt độ và tải nền giữa các lượt có thể ảnh hưởng thời gian.
