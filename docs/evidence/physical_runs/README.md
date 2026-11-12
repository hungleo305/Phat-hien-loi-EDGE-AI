# Chạy thử nhận diện và phân loại trên băng tải

Ngày thử: 11/11/2026. Ba đợt dùng cấu hình được xác nhận: LED 70/255, PWM 180/255, góc đặt servo 60°, chờ thu 350 ms, phơi sáng camera 1100. Một số hộp được chạy lặp; đơn vị là lượt kiểm định.

| Đợt | Lượt | PASS | DEFECT | Nhận diện đúng theo quan sát |
|---|---:|---:|---:|---:|
| #4 | 28 | 7 | 21 | 28/28 |
| #5 chạy lại | 28 | 7 | 21 | 28/28 |
| #6 | 30 | 7 | 23 | 30/30 |
| Tổng | 86 | 21 | 65 | 86/86 |

Các tệp `trial4.json`, `trial5_repeat.json`, `trial6.json` là bản ghi API của các đợt tương ứng. [summary.csv](summary.csv) tổng hợp số bản ghi và thời gian từ yêu cầu chụp đến trả kết quả.

Đánh giá đúng nhận diện dựa vào đối chiếu hộp thực tế và xác nhận của người vận hành. Các JSON ghi kết quả máy, không chứa bảng nhãn thật độc lập cho từng hộp. Không dùng riêng bộ đếm hoặc `delivered=true` để chứng minh nhận diện đúng hay servo gạt đúng. Thao tác gạt đúng được xác nhận qua quan sát trực tiếp; hồ sơ này không có phép đo sai số vị trí hoặc cảm biến xác nhận hướng ra của từng hộp.

Không đưa đợt #5 ban đầu vào thống kê vì thao tác thử không hợp lệ; dùng đợt #5 chạy lại. Bộ này là các lượt chạy thực, không cộng với số ảnh của bộ 466 ảnh đã lưu. Kết quả nhận diện đúng không thay thế đánh giá năng suất hoặc độ bền vận hành dài hạn.
