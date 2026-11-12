# So sánh thời gian kiểm định trên Pi và Acer

Ngày đo: 10/11/2026. Hai máy nhận cùng 11 mảng ảnh camera, gồm 5 PASS và 6 DEFECT; mỗi ảnh xử lý ba lần trên mỗi máy sau khởi động mô hình. Có 33 lần gọi trên mỗi máy, không phải 33 ảnh độc lập.

Chương trình, trọng số NCNN FP32 và mẫu tem giống nhau. Chạy CPU: Pi 4 luồng, Acer i5-11400H 6 luồng; không dùng GPU laptop. Đo toàn hàm kiểm định, không tính tải mô hình, đọc tệp, thu camera, UART hoặc cơ khí.

| Chỉ tiêu | Pi 4 | Acer |
|---|---:|---:|
| Đúng theo nhãn trên bộ 11 ảnh | 11/11 | 11/11 |
| Trung bình (s/ảnh) | 0,984 | 0,158 |
| Trung vị (s/ảnh) | 0,652 | 0,120 |
| p95 (s/ảnh) | 1,756 | 0,299 |

Tỷ số trung bình khoảng 6,22 lần. Quyết định trùng ở 33 cặp lần gọi. Bộ nhỏ có ảnh chụp lặp cùng hộp, không đại diện độ chính xác trên mọi hộp mới.

- [paired_by_image.csv](paired_by_image.csv): kết quả và thời gian theo ảnh.
- [paired_summary.json](paired_summary.json): cấu hình, phiên bản thư viện, mã băm runtime và số liệu tổng hợp.
- [thoi_gian_pi_acer.png](thoi_gian_pi_acer.png): biểu đồ kèm hồ sơ đo.
