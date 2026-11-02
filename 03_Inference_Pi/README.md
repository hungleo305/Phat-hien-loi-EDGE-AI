# THƯ MỤC 03: CODE CHẠY THỰC TẾ TRÊN RASPBERRY PI 4 (INFERENCE)

> **Ánh xạ thuyết minh đồ án:** Mục 3.2.3.4 (Thực nghiệm suy luận trên Raspberry Pi 4) và Kiến trúc kiểm định 3 tầng (Mục 3.2.2).

---

## 1. Danh sách các tệp trong thư mục

| Tên tệp | Vai trò |
|---|---|
| **`run_station.py`** | **Chương trình điều phối chính của trạm trên Pi:** Khởi tạo camera USB UVC `/dev/video0` (`cv2.VideoCapture`), mở cổng UART `/dev/serial0` kết nối ESP32, lắng nghe tín hiệu cảm biến quang và trả kết quả `RESULT`. |
| **`main_pipeline.py`** | **Pipeline suy luận AI 3 tầng kết hợp:**<br>• *Tầng 1:* Chạy mô hình toàn hộp NCNN ($640 \times 640$).<br>• *Tầng 2:* Chạy mô hình ngoại quan NCNN ($960 \times 960$).<br>• *Tầng 3:* Gọi `template_matching.py` căn chỉnh Homography và đối sánh mẫu NCC. |
| **`template_matching.py`** | Module kiểm định tem nhãn (Mục 3.2.2): Tính ma trận biến đổi phối cảnh Homography $3 \times 3$ và so khớp mẫu NCC (`cv2.matchTemplate`) đối với các vùng ROI ký hiệu QC. |
| **`guard_logic.py`** | Logic an toàn công nghiệp: Xử lý cơ chế ngắt sớm (Early-Exit) khi phát hiện lỗi vật lý rõ ràng để tiết kiệm chu kỳ CPU của Pi. |
| **`station_protocol.py`** | Bộ mã hóa / giải mã giao thức UART ASCII (`READY`, `HELLO`, `CAPTURE`, `RESULT`, `STATE`). |
| **`assets/`** | Chứa ảnh tem mẫu chuẩn (`approved_label.png`) và các template ROI cắt rời (`qc.png`, `year.png`, `inspector.png`, `logo.png`). |
| **`models/`** | Chứa 2 mô hình NCNN FP16 (`whole_balanced_ncnn_model` và `surface_finetuned_ncnn_model`) phục vụ nạp trực tiếp vào RAM Pi. |
| **`camera_profile.json`** | Cấu hình tham số phần cứng V4L2 của camera công nghiệp: độ phơi sáng cố định (Exposure), Gain, độ phân giải $1280 \times 720$. |

---

## 2. Lệnh khởi chạy trạm trên Pi

```bash
python run_station.py --root . --port /dev/serial0 --camera 0 --headless
```
*(Trên Pi thực tế, tiến trình này được hệ thống quản trị tự động qua dịch vụ `systemd: datn-station.service`).*

