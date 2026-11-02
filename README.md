# Thiết kế hệ thống Edge AI phát hiện lỗi sản phẩm trên dây chuyền sản xuất

**Đồ án tốt nghiệp Kỹ sư - Học viện Kỹ thuật Mật mã (KMA)**  
**Chuyên ngành:** An toàn thông tin / Hệ thống nhúng & Edge AI  
**Sinh viên thực hiện:** Chu Mạnh Hùng  
**Mục tiêu:** Tự động phát hiện và phân loại lỗi vỏ hộp bao bì carton trên băng tải công nghiệp Stop & Go thời gian thực bằng camera USB UVC, vi máy tính Raspberry Pi 4 Model B, vi điều khiển ESP32 và giao diện giám sát SCADA Web Dashboard.

---

## Cấu trúc thư mục mã nguồn

```
DATN_Source/
├── 01_Training/           # Huấn luyện mô hình thị giác máy tính YOLOv8n (PyTorch)
├── 02_Optimization/       # Tối ưu hóa đồ thị tĩnh & Lượng tử hóa bán chính xác NCNN FP16
├── 03_Inference_Pi/       # Đường ống suy luận 3 tầng thời gian thực trên Raspberry Pi 4
├── 04_ESP32_Firmware/     # Firmware C FreeRTOS điều khiển băng tải Stop & Go và servo gạt
└── 05_Dashboard/          # Máy chủ SCADA Web Dashboard giám sát và điều khiển vận hành
```

---

## Chi tiết các mô-đun

### 📁 01_Training: Huấn luyện AI (YOLOv8n)
- `train.py`: Huấn luyện mô hình phát hiện vỏ hộp tổng thể (`best.pt`, mAP@0.5 > 99%).
- `train_surface.py`: Huấn luyện tinh chỉnh mô hình phát hiện khuyết tật bề mặt vi mô (`best_surface.pt`).
- `evaluate.py`: Đánh giá ma trận nhầm lẫn (Confusion Matrix) và độ chính xác mAP.
- `data.yaml`: Khai báo tập dữ liệu và các nhãn phân loại (`PASS`, `DEFECT`).

### 📁 02_Optimization: Chuyển đổi & Lượng tử hóa NCNN FP16
- `export_ncnn.py` & `export_ncnn.sh`: Quy trình xuất mô hình từ PyTorch sang ONNX/TorchScript và biên dịch sang NCNN (`model.param`, `model.bin`).
- Tối ưu hóa gộp lớp (Conv + BatchNorm + SiLU) và lượng tử hóa FP16, khai thác tập lệnh SIMD ARM NEON trên Cortex-A72.
- `ncnn_models/`: Chứa 2 mô hình NCNN chính thức triển khai trên Pi 4 (`tier1_whole_balanced` và `tier2_surface_finetuned`).

### 📁 03_Inference_Pi: Suy luận thời gian thực trên Raspberry Pi 4
- `main_pipeline.py`: Đường ống suy luận 3 tầng với cơ chế thoát sớm (**Early-Exit**):
  - **Tầng 1:** Nhận diện hộp carton tổng thể và bắt lỗi biến dạng hình học lớn (~140ms).
  - **Tầng 2:** Kiểm định tem nhãn dán, năm ('2026' vs '2025'), trạng thái QC ('PASSED' vs 'FAILED') và vết bôi bẩn/rách tem.
  - **Tầng 3:** Quét khuyết tật bề mặt vi mô khi tem đã hợp lệ, tích hợp bộ lọc chống báo động giả logo KMA.
- `template_matching.py`: So khớp đặc trưng ORB, nắn góc phối cảnh Homography USAC_MAGSAC (320x320) và tương quan chéo chuẩn hóa (NCC).
- `run_station.py` & `station_protocol.py`: Quản lý chu trình Stop & Go, đồng bộ cảm biến và giao thức truyền nhận UART với ESP32.

### 📁 04_ESP32_Firmware: Firmware điều khiển chấp hành (ESP-IDF)
- `ESP32_Firmware.c`: Kiến trúc FreeRTOS đa tác vụ (`control_task` chu kỳ 10ms, `console_task` gỡ lỗi), khử rung cảm biến quang 30ms và nhịp tim an toàn (Heartbeat).
- `stopgo.c`: Máy trạng thái hữu hạn Stop & Go gồm 10 trạng thái (`SG_STOPPED` đến `SG_FAULT`), cơ chế dừng 150ms chống nhòe ảnh và hàng đợi vòng tròn FIFO 8 hộp.
- `servo.c`: Điều khiển servo SG90 bằng xung PWM 50Hz với **Profile chuyển động 3 bước dứt khoát** ($0^\circ \rightarrow 12^\circ \rightarrow 23^\circ \rightarrow 35^\circ$ trong 150ms), triệt tiêu rung rơ và kẹt cơ.
- `build/ESP32_Firmware.bin`: File nhị phân nạp sẵn vào vi điều khiển ESP32.

### 📁 05_Dashboard: Giao diện giám sát SCADA & Điều khiển
- `server.py`: Web server nhúng trên Pi 4 (`ThreadingHTTPServer`), hỗ trợ API RESTful (`/api/state`, `/api/runs`, `/api/command`) và luồng video MJPEG độ trễ thấp (<150ms).
- `index.html`, `app.js`, `dashboard.css`: Giao diện điều khiển cảm ứng, hiển thị camera trực tiếp, nút Start/Stop, tùy chỉnh thông số động cơ/đèn LED, và tạo phiên vận hành có đặt tên.
