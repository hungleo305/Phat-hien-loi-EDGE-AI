# Phân hệ 02 — Chuyển đổi và tối ưu hóa mô hình NCNN

Thư mục này cung cấp công cụ chuyển đổi hai mô hình YOLOv8n từ định dạng PyTorch (`.pt`) sang định dạng **NCNN** để tăng tốc suy luận trên vi xử lý ARM Cortex-A72 của **Raspberry Pi 4**.

---

## 1. Lý do lựa chọn NCNN FP32 cho bản vận hành chính thức

Trên Raspberry Pi 4 (không có GPU rời hỗ trợ CUDA), việc chạy trực tiếp mô hình qua khung NCNN giúp giảm chi phí khởi tạo và tận dụng tập lệnh вектор ARM NEON. Để chọn cấu hình tối ưu giữa độ chính xác và tốc độ, hai phép thử nghiệm thực tế đã được thực hiện trên cùng bộ **466 ảnh** tại Raspberry Pi 4:

1. **Đối chiếu định dạng trọng số `NCNN FP32` và `NCNN FP16`** ([xem hồ sơ `docs/evidence/fp16/`](../docs/evidence/fp16/README.md)):
   - Cả hai định dạng đều cho kết quả quyết định khớp nhãn **466/466 ảnh (100%)**.
   - Tuy nhiên, thời gian xử lý trung bình của **FP32 là `1071,8 ms/ảnh`** (trung vị `802,9 ms`), nhanh hơn nhẹ so với **FP16 là `1096,0 ms/ảnh`** (trung vị `811,8 ms`) trên CPU Cortex-A72 của Pi 4.
2. **Đối chiếu kích thước đầu vào mô hình bề mặt `960`, `832` và `768 px`** ([xem hồ sơ `docs/evidence/surface_sizes/`](../docs/evidence/surface_sizes/README.md)):
   - Giữ kích thước **`960 × 960`** đạt **466/466**, trong khi giảm xuống `832` hoặc `768` làm bỏ lọt `40` ảnh lỗi và gây kích hoạt thêm nhánh kiểm tra dự phòng khiến tổng thời gian trung bình tăng lên (`1124,7 ms` và `1378,1 ms`).

Vì vậy, hệ thống giữ **2 mô hình NCNN FP32 (`640×640` cho toàn hộp và `960×960` cho bề mặt)** làm bản chuẩn trong [`../03_Inference_Pi/runtime/models/`](../03_Inference_Pi/runtime/models/).

---

## 2. Danh mục tệp trong thư mục

| Tên tệp | Chức năng |
|---|---|
| [`export_ncnn.py`](export_ncnn.py) | Kịch bản Python đọc 2 checkpoint `.pt` chuẩn trong `03_Inference_Pi/runtime/models/`, xuất ứng viên NCNN sang thư mục mới và ghi mã băm SHA-256 kèm dung lượng vào `export_manifest.json`. |
| [`export_ncnn.bat`](export_ncnn.bat) | Kịch bản gọi nhanh `export_ncnn.py` trên Windows. |
| [`export_ncnn.sh`](export_ncnn.sh) | Kịch bản gọi nhanh `export_ncnn.py` trên Linux / Raspberry Pi OS. |

---

## 3. Hướng dẫn xuất thử nghiệm ứng viên NCNN mới

Từ thư mục gốc của kho mã nguồn (trong môi trường đã cài đặt `ultralytics`):

```powershell
# Trên Windows PowerShell
python 02_Optimization/export_ncnn.py --output-root F:/DATN/Cong_cu_phat_trien/work/ncnn_candidate_run
```

```bash
# Trên Linux / Raspberry Pi
bash 02_Optimization/export_ncnn.sh /tmp/ncnn_candidate_run
```

*Lưu ý*: Công cụ luôn xuất mô hình vào một thư mục đầu ra mới để kiểm tra độc lập, tuyệt đối không ghi đè trực tiếp lên gói `03_Inference_Pi/runtime/models/` đang vận hành.
