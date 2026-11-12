# Hệ thống kiểm định hộp bằng Edge AI

Đồ án của Chu Mạnh Hùng: Raspberry Pi 4 nhận ảnh camera và kiểm định hộp; ESP32 điều khiển băng tải, cảm biến, đèn và servo phân loại. Dashboard dùng để vận hành và xem kết quả trong mạng cục bộ.

## Đọc kho mã theo thứ tự

| Phần | Nội dung | Điểm bắt đầu |
|---|---|---|
| 01 | Huấn luyện và đo chỉ số hai mô hình YOLOv8n | [01_Training](01_Training/README.md) |
| 02 | Xuất ứng viên NCNN FP16, đối chiếu với FP32 đang dùng | [02_Optimization](02_Optimization/README.md) |
| 03 | Runtime AI, model, mẫu tem và camera profile | [03_Inference_Pi](03_Inference_Pi/README.md) |
| 04 | Firmware ESP32, đấu nối, build và vận hành | [04_ESP32_Firmware](04_ESP32_Firmware/README.md) |
| 05 | Điều phối camera/UART và dashboard | [05_Dashboard](05_Dashboard/README.md) |
| docs | Lưu đồ và dữ liệu làm bằng chứng cho báo cáo | [Hồ sơ thực nghiệm](docs/evidence/README.md) |

Mỗi loại mã/model chỉ có một bản trong kho: runtime AI tại `03_Inference_Pi/runtime`, trạm và giao diện tại `05_Dashboard/station`, firmware tại `04_ESP32_Firmware`. Checkpoint PyTorch và model NCNN cùng nằm trong runtime để kiểm tra nguồn gốc; không sao chép model vào từng module.

## Hệ thống hoạt động thế nào

1. Cảm biến chụp báo hộp; ESP32 dừng băng tải và gửi `CAPTURE` kèm phiên/ID hộp.
2. Pi lấy ảnh rồi gửi `CAPTURED`; băng tải có thể chạy tiếp trong lúc AI xử lý.
3. AI chạy toàn hộp NCNN FP32 640 → kiểm tra tem ORB/Homography/NCC → bề mặt NCNN FP32 960 khi cần. Có kết luận sớm để giảm tính toán.
4. Pi gửi `RESULT` theo đúng phiên/ID; ESP32 lưu vào FIFO. Tại cửa gạt, chỉ dừng chờ nếu chưa có kết quả; hộp lỗi được gạt khi bật chế độ phân loại.

DEFECT được ưu tiên khi hộp có lỗi dù có hay không có tem. REVIEW biểu thị chưa đủ chắc chắn và được gửi thành ERROR, không tự chuyển PASS. PWM là mức điều khiển, không phải vận tốc đo được; góc servo là góc ra lệnh, không phải góc có phản hồi cảm biến.

## Kiểm tra kho mã

Từ gốc kho, dùng môi trường Python có các thư viện trong [requirements_pi.txt](03_Inference_Pi/runtime/requirements_pi.txt):

```bash
python tools/verify_repository.py
python 03_Inference_Pi/runtime/self_check.py --backend ncnn
python 05_Dashboard/tests/check_runs.py
python 05_Dashboard/tests/check_defaults.py
node 05_Dashboard/tests/check_image.cjs
node --check 05_Dashboard/station/dashboard.js
```

Self-check gồm 5 ảnh mẫu; đây là kiểm tra hồi quy nhỏ. Lệnh trên không thay thế kiểm thử hộp mới, camera thật hoặc chạy bền cơ khí.

## Bản chạy trên Pi và bản nguồn

Máy Pi hiện tại chạy dịch vụ user `datn-station.service`, tại `/home/cmh/Pi4_EdgeAI/current` → `production/pi_production_20261101`. Kho Git là mã nguồn được quản lý; commit/push không tự triển khai lên Pi. [Hướng dẫn vận hành](docs/VAN_HANH.md) giải thích địa chỉ dashboard và cách kiểm tra dịch vụ. [Cấu trúc và phụ thuộc](docs/KIEN_TRUC.md) giải thích đường đi của mã và dữ liệu.

Mặc định Pi áp dụng khi trạm dừng và cảm biến trống: LED 70, PWM 180, góc 60°, chờ thu 350 ms; camera lưu phơi sáng 1100. Firmware `SINGLE_TASK_UART2_20261109` đã được người vận hành xác nhận nạp. Gạt hộp đã được quan sát hoạt động; chưa có đánh giá chạy bền dài hạn.

## Đọc đúng kết quả thực nghiệm

- Bộ 466 ảnh là hồi quy có dùng trong phát triển, không phải 466 hộp mới độc lập.
- Ba đợt chạy thực tế đã đối chiếu có 86 lượt (21 PASS, 65 DEFECT); có hộp được chạy lại. Quan sát gạt và thống kê nhận diện là hai loại bằng chứng khác nhau.
- So sánh Pi–Acer dùng 11 tệp ảnh, ba lượt/tệp/máy. Ba tệp PASS cùng nội dung ảnh. Trung bình hàm kiểm định: Pi 0,984 s, Acer 0,158 s; chưa gồm chụp, UART và cơ khí.

Xem điều kiện, số đo và giới hạn tại [docs/evidence](docs/evidence/README.md). Dữ liệu huấn luyện/ảnh nguồn, khóa SSH, bản ghi vận hành và thư mục build không được đưa vào Git.
