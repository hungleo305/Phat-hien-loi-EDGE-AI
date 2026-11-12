# Hồ sơ dữ liệu và thực nghiệm dùng trong báo cáo đồ án

Thư mục này lưu trữ công khai toàn bộ bảng số liệu, nhật ký kết quả (`CSV`, `JSON`, `YAML`) và hình ảnh minh chứng cho các thực nghiệm trong báo cáo **Thiết kế hệ thống Edge AI phát hiện lỗi sản phẩm trên dây chuyền sản xuất** của sinh viên **Chu Mạnh Hùng**.

---

## 1. Bảng ánh xạ tài liệu tham khảo và mục trong báo cáo

| Tài liệu tham khảo | Mục / Bảng trong báo cáo | Nội dung hồ sơ thực nghiệm | Thư mục lưu trữ |
|---|---|---|---|
| **[1]** | Mục `3.2.1`, `3.2.2` (`Bảng 3.1`–`3.3`) | Kiểm kê bộ dữ liệu V4 (295 ảnh), bộ bề mặt kết hợp (559 ảnh), cấu hình và chỉ số huấn luyện 2 mô hình YOLOv8n | [`training_data/`](training_data/README.md) |
| **[2]** | Mục `3.4` (`Hình 3.17`–`3.19`) | Giao diện Web Dashboard thực tế khi giám sát trạm, cài đặt thông số và xem lịch sử phiên chạy | [`dashboard/`](dashboard/README.md) |
| **[3]** | Mục `3.5.1` (`Bảng 3.8`) | Kết quả chạy kiểm tra hồi quy toàn bộ pipeline NCNN FP32 trên **466 ảnh** tại Raspberry Pi 4 | [`pi466/`](pi466/README.md) |
| **[4]** | Mục `3.5.3` (`Bảng 3.10`, `3.11`) & `Phụ lục A` (`Bảng A.1`) | Nhật ký **3 đợt chạy thử nghiệm thực tế** trên băng tải (86 lượt kiểm định hộp) | [`physical_runs/`](physical_runs/README.md) |
| **[5]** | Mục `3.2.3` (`Bảng 3.4`) | Đối chiếu tốc độ/độ chính xác giữa **NCNN FP32 và FP16**, và so sánh **kích thước đầu vào mô hình bề mặt (`960`, `832`, `768 px`)** | [`fp16/`](fp16/README.md), [`surface_sizes/`](surface_sizes/README.md) |
| **[6]** | Mục `3.5.2` (`Bảng 3.9`) & `Phụ lục B` (`Bảng B.1`) | Đối chiếu thời gian xử lý từng mẫu ảnh giữa **Raspberry Pi 4** và **Laptop Acer** trên cùng bộ 11 tệp ảnh | [`pi_acer/`](pi_acer/README.md) |

---

## 2. Phân biệt rõ ý nghĩa của từng bộ dữ liệu trong đồ án

Để người đọc dễ theo dõi, các con số mẫu ảnh trong báo cáo thuộc các tập thực nghiệm có mục đích khác nhau (không cộng gộp thành một tổng duy nhất):

1. **Bộ dữ liệu V4 (`295 ảnh`)**: Bộ ảnh gốc dùng để phát triển và đánh giá mô hình phát hiện toàn hộp, được chia tách theo từng hộp vật lý thành **205 ảnh huấn luyện**, **40 ảnh xác thực (`valid`)** và **50 ảnh kiểm thử (`test`)**.
2. **Bộ huấn luyện bề mặt kết hợp (`559 ảnh`)**: Dùng riêng để huấn luyện mô hình tìm vết rách/xước cục bộ (`960×960`), gồm **354 ảnh** bổ sung từ giai đoạn trước kết hợp với **205 ảnh huấn luyện V4**. Mô hình này được đánh giá trên tập **40 ảnh xác thực V4**.
3. **Bộ kiểm tra hồi quy trên Pi 4 (`466 ảnh`)**: Tập ảnh lưu trữ (gồm `189 PASS` và `277 DEFECT` từ 3 nguồn: `original_245`, `pi_regression_80`, `camera_sessions_141`) dùng để kiểm tra độ ổn định và đo thời gian xử lý của toàn bộ pipeline kết hợp (`YOLOv8n + ORB/Homography/NCC`) trên Raspberry Pi 4.
4. **Bộ đối chiếu tốc độ Pi 4 – Laptop Acer (`11 tệp ảnh`)**: Gồm `6` tệp hộp lỗi (`DEFECT`) và `5` tệp hộp đạt (`PASS`, trong đó mẫu `09–11` có cùng nội dung ảnh). Mỗi tệp được xử lý lặp lại **3 lần trên mỗi máy** (tổng cộng `33` lần đo/máy) để so sánh tốc độ tính toán thuần túy của CPU.
5. **Ba đợt chạy thử trên băng tải thực tế (`86 lượt kiểm định`)**: Gồm đợt `#4` (`28` lượt), đợt `#5 chạy lại` (`28` lượt) và đợt `#6` (`30` lượt), tổng cộng **`21` lượt `PASS`** và **`65` lượt `DEFECT`**, đánh giá sự phối hợp toàn trình giữa cảm biến, băng tải, camera, AI, UART2 và cơ cấu servo phân loại.

---

## 3. Kiểm tra tính toàn vẹn của hồ sơ số liệu

Tất cả 29 tệp trong thư mục `docs/evidence/` đều được niêm phong mã băm SHA-256 trong tệp [`SHA256SUMS`](SHA256SUMS) và được kiểm tra tự động bằng lệnh:

```bash
python tools/verify_repository.py
```
