# Hồ sơ dữ liệu và thực nghiệm dùng trong báo cáo DATN

Thư mục này công bố nguồn số liệu tự thực hiện được dẫn trong báo cáo **Thiết kế hệ thống Edge AI phát hiện lỗi sản phẩm trên dây chuyền sản xuất** của Chu Mạnh Hùng. Ngày tập hợp hồ sơ: 12/11/2026. Ngày thực nghiệm được ghi riêng trong từng nhóm.

| Tài liệu tham khảo trong báo cáo | Nội dung | Hồ sơ |
|---|---|---|
| [7] | Chạy lại 466 ảnh trên Pi | [pi466](pi466/) |
| [8] | So sánh FP32/FP16 và kích thước đầu vào bề mặt | [fp16](fp16/), [surface_sizes](surface_sizes/) |
| [9] | So sánh Pi với Acer trên cùng 11 ảnh | [pi_acer](pi_acer/) |
| [10] | Giao diện dashboard đang sử dụng | [dashboard](dashboard/) |
| [11] | Ba đợt chạy thử có 86 lượt kiểm định | [physical_runs](physical_runs/) |
| [20] | Thành phần dữ liệu và kết quả huấn luyện | [training_data](training_data/) |

Các CSV/JSON số liệu được sao chép nguyên nội dung từ hồ sơ thực nghiệm. README giải thích phương pháp, đơn vị và phạm vi sử dụng. `SHA256SUMS` cho phép kiểm tra tính toàn vẹn các tệp công bố.

## Phân biệt dữ liệu

- **295 ảnh V4**: bộ phát triển mô hình, gồm 205 ảnh huấn luyện, 40 ảnh xác thực và 50 ảnh kiểm thử.
- **559 ảnh**: dữ liệu huấn luyện mô hình bề mặt, gồm 354 ảnh bổ sung từ bộ dữ liệu giai đoạn trước và 205 ảnh huấn luyện V4.
- **466 ảnh**: ảnh đã lưu để chạy lại toàn chương trình; kết quả không phải phép đánh giá độc lập trên 466 hộp mới.
- **11 ảnh**: bộ so sánh thời gian Pi–Acer, mỗi ảnh xử lý ba lần trên mỗi máy.
- **86 lượt**: kết quả chạy thử trên băng tải; có hộp được chạy lặp.

Các số trên có mục đích khác nhau và một phần cùng nguồn ảnh, không cộng thành tổng số mẫu độc lập. Hồ sơ này **không kèm toàn bộ ảnh nguồn của bộ huấn luyện và bộ 466 ảnh**. Các bảng, nhật ký kết quả và kiểm kê dữ liệu cho phép kiểm tra cách tính; để chạy lại toàn bộ thực nghiệm còn cần ảnh nguồn và đúng môi trường thực thi. Mô hình và chương trình được lưu ở các mô-đun khác trong kho mã.

Khi trích dẫn, nên dùng liên kết theo commit chứa bản hồ sơ này để tránh thay đổi nội dung về sau. Các đường dẫn máy tính trong một số tệp gốc là dấu vết môi trường đo, không phải đường dẫn tải dữ liệu.
