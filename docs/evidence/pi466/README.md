# Kiểm tra lại 466 ảnh trên Raspberry Pi 4

Ngày đo: 01/11/2026. Chạy hàm kiểm định NCNN FP32 trên ảnh đã lưu; không gồm thu camera, UART hoặc chuyển động băng tải. Đây là phép kiểm tra lại bộ dữ liệu đã dùng trong phát triển.

| Nguồn ảnh | PASS theo nhãn đối chiếu | DEFECT theo nhãn đối chiếu | Tổng |
|---|---:|---:|---:|
| `original_245` — ảnh hộp ban đầu | 80 | 165 | 245 |
| `pi_regression_80` — ảnh kiểm thử trên Pi | 20 | 60 | 80 |
| `camera_sessions_141` — ảnh lưu từ các đợt chụp camera | 89 | 52 | 141 |
| Tổng | 189 | 277 | 466 |

Kết quả: 466/466 quyết định khớp nhãn đối chiếu đã ghi. AI trung bình 889,1 ms, trung vị 720,0 ms, lớn nhất 1603,2 ms.

- [results.csv](results.csv): một hàng/một ảnh, gồm nhóm dữ liệu, tên ảnh, SHA-256, nhãn đối chiếu `truth`, kết luận `decision`, đối chiếu `correct`, lý do và thời gian `ai_ms`.
- [summary.json](summary.json): kết quả tổng hợp gốc và thống kê theo nhóm.

`truth` là nhãn đối chiếu trong hồ sơ, không phải cam kết rằng nhãn được gán mù độc lập với quá trình phát triển. Nhiều ảnh thuộc cùng hộp; không suy ra số hộp độc lập từ số ảnh.
