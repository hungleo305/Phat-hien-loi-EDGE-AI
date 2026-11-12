# Hệ thống kiểm định chất lượng và phân loại hộp sản phẩm bằng Edge AI

**Đồ án tốt nghiệp — Sinh viên thực hiện: Chu Mạnh Hùng**

Kho mã nguồn này chứa toàn bộ chương trình, mô hình AI, firmware vi điều khiển, giao diện giám sát và hồ sơ số liệu thực nghiệm của đề tài **Thiết kế hệ thống Edge AI phát hiện lỗi sản phẩm trên dây chuyền sản xuất**.

---

## 1. Tổng quan hệ thống

Hệ thống tự động kiểm tra ngoại quan hộp carton và tem nhãn trên băng tải theo cơ chế **Dừng – Chụp – Kiểm định – Phân loại (Stop & Go)**, kết hợp giữa tính toán biên (**Raspberry Pi 4**) và điều khiển thời gian thực (**ESP32**):

1. **Phát hiện hộp và chụp ảnh**: Khi hộp đến cảm biến tại buồng chụp, **ESP32** dừng băng tải, cấp mã định danh (`ID`) vào hàng đợi **FIFO** và gửi bản tin `CAPTURE` qua UART2. **Raspberry Pi 4** đọc khung hình từ camera USB, trả lời `CAPTURED` để băng tải có thể chạy tiếp ngay trong lúc AI đang xử lý ảnh.
2. **Kiểm định ảnh 3 bước có kết luận sớm (Early-Exit)**:
   - **Bước 1 — Phát hiện toàn hộp (`YOLOv8n NCNN FP32`, `640×640`)**: Định vị hộp và phát hiện lỗi biến dạng/móp méo nặng (cổng `G1`, ngưỡng `0,70`). Nếu phát hiện lỗi nặng, kết luận `DEFECT` ngay.
   - **Bước 2 — Kiểm định tem nhãn (`ORB + Homography USAC_MAGSAC + NCC`)**: Định vị tem trên vùng hộp (hoặc toàn ảnh), căn chỉnh phối cảnh về `320×320 px`, kiểm tra 6 vùng nội dung (`logo`, `school`, `project`, `inspector`, `qc`, `year`), phát hiện thiếu tem (`NOLABEL` -> `DEFECT`), sai trường `QC PASSED` / năm `2026`, vết bẩn/vẽ thêm hoặc rách tem lộ nền carton (cổng `G3`).
   - **Bước 3 — Phát hiện lỗi bề mặt cục bộ (`YOLOv8n NCNN FP32`, `960×960`)**: Chỉ kích hoạt khi hộp và tem đã hợp lệ ở 2 bước đầu để tìm vết rách, xước, thủng nhỏ trên vỏ hộp (cổng `G2`, ngưỡng `0,05`, tỷ lệ diện tích `≤ 0,20`, có loại trừ vùng logo bằng đa giác Homography).
3. **Phân loại tại cửa gạt**: Pi gửi kết quả `RESULT` (`PASS`, `DEFECT` hoặc `ERROR`) về ESP32 theo đúng phiên và `ID`. Khi hộp đến cảm biến cửa gạt, ESP32 tra kết quả đầu hàng đợi FIFO: nếu là `DEFECT` (và đang bật chế độ phân loại `SORT`), servo SG90 quay góc gạt để đẩy hộp sang nhánh loại; nếu là `PASS`, hộp đi thẳng. Trường hợp `REVIEW` (ảnh mờ/khuất chưa đủ căn cứ) được chuyển thành `ERROR` để dừng an toàn, tuyệt đối không tự quy thành `PASS`.

---

## 2. Cấu trúc kho mã nguồn

Mỗi thành phần trong kho chỉ giữ **một nguồn chuẩn duy nhất (Single Source of Truth)**, không sao chép trùng lặp mô hình hay giao diện giữa các thư mục:

| Thư mục | Vai trò trong hệ thống | Tài liệu chi tiết |
|---|---|---|
| [`01_Training/`](01_Training/README.md) | Kịch bản huấn luyện và đánh giá 2 mô hình YOLOv8n (toàn hộp `640×640` và bề mặt `960×960`) | [01_Training/README.md](01_Training/README.md) |
| [`02_Optimization/`](02_Optimization/README.md) | Công cụ chuyển đổi mô hình PyTorch (`.pt`) sang định dạng NCNN và đối chiếu FP32/FP16 | [02_Optimization/README.md](02_Optimization/README.md) |
| [`03_Inference_Pi/`](03_Inference_Pi/README.md) | Gói `runtime/` chạy trên Raspberry Pi 4 (pipeline AI, bộ kiểm tra tem, trọng số NCNN FP32 & PyTorch, cấu hình camera) | [03_Inference_Pi/README.md](03_Inference_Pi/README.md) |
| [`04_ESP32_Firmware/`](04_ESP32_Firmware/README.md) | Firmware C (ESP-IDF 5.3.5) cho ESP32: máy trạng thái Stop&Go, hàng đợi FIFO, điều khiển motor/LED/servo và giao thức UART2 | [04_ESP32_Firmware/README.md](04_ESP32_Firmware/README.md) |
| [`05_Dashboard/`](05_Dashboard/README.md) | Phần mềm trạm điều phối (`station/`) kết nối Camera – AI – UART2 và giao diện Web Dashboard giám sát, điều khiển, lưu lịch sử CSV/JSON | [05_Dashboard/README.md](05_Dashboard/README.md) |
| [`docs/diagrams/`](docs/diagrams/README.md) | Bộ sơ đồ kiến trúc, đấu nối phần cứng và lưu đồ thuật toán chèn trong báo cáo đồ án | [docs/diagrams/README.md](docs/diagrams/README.md) |
| [`docs/evidence/`](docs/evidence/README.md) | Hồ sơ dữ liệu, nhật ký thực nghiệm và bảng số liệu gốc được trích dẫn trong báo cáo | [docs/evidence/README.md](docs/evidence/README.md) |
| [`tools/`](tools/verify_repository.py) | Công cụ kiểm tra tự động mã băm SHA-256, cú pháp Python và liên kết tài liệu trong kho | [docs/KIEN_TRUC.md](docs/KIEN_TRUC.md) |

Xem thêm:
- [Kiến trúc mã nguồn và luồng dữ liệu (`docs/KIEN_TRUC.md`)](docs/KIEN_TRUC.md)
- [Hướng dẫn vận hành trạm thực tế (`docs/VAN_HANH.md`)](docs/VAN_HANH.md)

---

## 3. Tóm tắt kết quả thực nghiệm chính

Toàn bộ dữ liệu đối chiếu dưới đây được lưu trữ công khai kèm mã kiểm tra `SHA256SUMS` tại [`docs/evidence/`](docs/evidence/README.md):

| Hạng mục đánh giá | Quy mô và điều kiện thử nghiệm | Kết quả đạt được | Hồ sơ minh chứng |
|---|---|---|---|
| **Huấn luyện YOLOv8n** | Bộ V4 gồm **295 ảnh** (205 train, 40 val, 50 test); bộ bề mặt kết hợp **559 ảnh** | Toàn hộp (`640`): `mAP@50 = 0,726` (tập test)<br>Bề mặt (`960`): `mAP@50 = 0,391` (tập val) | [`training_data/`](docs/evidence/training_data/README.md) |
| **Lựa chọn NCNN FP32 vs FP16** | Chạy cùng pipeline trên **466 ảnh** tại Raspberry Pi 4 | Khớp nhãn `466/466`; **FP32 (`1071,8 ms`)** nhanh hơn FP16 (`1096,0 ms`) -> Chọn **FP32** | [`fp16/`](docs/evidence/fp16/README.md) |
| **Kích thước đầu vào bề mặt** | Thử nghiệm `960`, `832` và `768 px` trên **466 ảnh** tại Pi 4 | Mức **960 px** đạt `466/466` (`1097,6 ms`); giảm xuống `832`/`768` làm lọt 40 ảnh lỗi | [`surface_sizes/`](docs/evidence/surface_sizes/README.md) |
| **Kiểm tra hồi quy trên Pi 4** | Chạy hàm kiểm định NCNN FP32 trên **466 ảnh** đã lưu (189 PASS, 277 DEFECT) | Khớp nhãn đối chiếu **`466/466` (100%)**; thời gian AI trung bình **`889,1 ms/ảnh`** (trung vị `720,0 ms`) | [`pi466/`](docs/evidence/pi466/README.md) |
| **Đối chiếu tốc độ Pi 4 và Laptop Acer** | Cùng **11 mẫu ảnh** × 3 lần chạy = 33 lượt/máy (chạy CPU, cùng mô hình) | Khớp quyết định `11/11`; Pi 4 trung bình **`0,984 s/ảnh`**, Acer **`0,158 s/ảnh`** (nhanh hơn `6,22×`) | [`pi_acer/`](docs/evidence/pi_acer/README.md) |
| **Chạy thử nghiệm trên băng tải thật** | **3 đợt chạy liên hoàn** (#4, #5 chạy lại, #6) với tổng cộng **86 lượt hộp** | Nhận diện và phân loại đúng **`86/86` lượt** (`21 PASS`, `65 DEFECT`); thời gian trung bình từ chụp đến có kết quả `1,42 – 1,60 s` | [`physical_runs/`](docs/evidence/physical_runs/README.md) |

---

## 4. Hướng dẫn kiểm tra nhanh kho mã nguồn

Từ thư mục gốc của kho mã (sử dụng môi trường Python đã cài đặt các thư viện trong [`03_Inference_Pi/runtime/requirements_pi.txt`](03_Inference_Pi/runtime/requirements_pi.txt) và Node.js):

```bash
# 1. Kiểm tra mã băm SHA-256 (manifest + evidence), cú pháp Python và liên kết Markdown
python tools/verify_repository.py

# 2. Chạy tự kiểm tra (self-check) pipeline AI NCNN trên 5 ảnh mẫu chuẩn
python 03_Inference_Pi/runtime/self_check.py --backend ncnn

# 3. Kiểm tra logic quản lý phiên chạy, thông số mặc định và giao diện Dashboard
python 05_Dashboard/tests/check_runs.py
python 05_Dashboard/tests/check_defaults.py
node 05_Dashboard/tests/check_image.cjs
node --check 05_Dashboard/station/dashboard.js
```

### Thông số cấu hình chuẩn đang vận hành trên trạm thực tế
- **Dịch vụ trên Raspberry Pi 4**: `datn-station.service` (chạy tại `/home/cmh/Pi4_EdgeAI/current`), cung cấp Dashboard tại `http://127.0.0.1:8768` (hoặc qua cổng `8769` trên laptop thông qua SSH tunnel).
- **Thông số thiết bị mặc định khi khởi động ở trạng thái dừng (`STOPPED`)**: Đèn buồng chụp `LIGHT = 70/255`, động cơ băng tải `SPEED (PWM) = 180/255`, góc gạt servo `SERVO_ANGLE = 60°`, thời gian giữ gạt `SERVO_HOLD = 350 ms`, phơi sáng camera UVC `exposure_time_absolute = 1100`.
- **Firmware ESP32**: Bản `SINGLE_TASK_UART2_20261109` (ESP-IDF 5.3.5), giao tiếp với Pi qua UART2 (`115200 bps`, GPIO17 TX / GPIO16 RX).
