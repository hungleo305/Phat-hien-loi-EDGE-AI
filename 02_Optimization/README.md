# THƯ MỤC 02: CHUYỂN ĐỔI & TỐI ƯU HÓA MÔ HÌNH (OPTIMIZATION)

> **Ánh xạ thuyết minh đồ án:** Mục 3.2.3.3 (Chuyển đổi NCNN và thử nghiệm trọng số FP16).

---

## 1. Danh sách các tệp trong thư mục

| Tên tệp | Vai trò |
|---|---|
| **`export_ncnn.py`** | Xuất hai checkpoint production thành **ứng viên NCNN FP16 riêng** bằng `half=True`; kiểm tra marker FP16 và ghi manifest. Không ghi đè model trên Pi. |
| **`export_ncnn.sh`** | Script Bash ghi chú 4 bước dòng lệnh kinh điển: PyTorch $\rightarrow$ ONNX $\rightarrow$ `onnx2ncnn` $\rightarrow$ `ncnnoptimize` FP16. |
| **`export_ncnn.bat`** | Script chạy chuyển đổi trên hệ điều hành Windows. |
| **`ncnn_models/tier1_whole_balanced/`** | Thư mục mô hình NCNN Tầng 1 đã tối ưu (gồm `model.ncnn.param` và `model.ncnn.bin`). |
| **`ncnn_models/tier2_surface_finetuned/`** | Thư mục mô hình NCNN Tầng 2 đã tối ưu (gồm `model.ncnn.param` và `model.ncnn.bin`). |

---

## 2. Các tệp mô hình NCNN nhị phân quan trọng

Mỗi thư mục mô hình NCNN gồm 2 tệp nhị phân cốt lõi:
1. **`model.ncnn.param`**: Tệp văn bản mô tả cấu trúc đồ thị mạng nơ-ron sau khi đã áp dụng **gộp lớp (Layer Fusion)**: hợp nhất các lớp `Convolution + BatchNormalization + SiLU` thành một khối tính toán duy nhất, triệt tiêu việc ghi đệm trung gian vào RAM.
2. **`model.ncnn.bin`**: Tệp trọng số NCNN. Định dạng NCNN không tự chứng minh FP16: gói production ngày 01/11 có trọng số FP32; ứng viên xuất ngày 03/11 dùng FP16 và cần kiểm tra hồi quy, đo trên Pi trước khi triển khai.

---

## 3. Lệnh chạy xuất mô hình

```powershell
& 'C:\Users\ACER\miniconda3\envs\doan_ai\python.exe' 'DATN_Source\02_Optimization\export_ncnn.py' --output-root 'Cong_cu_phat_trien\work\fp16_thu_nghiem_moi'
```
Thư mục output phải chưa tồn tại. Script chỉ tạo ứng viên; không thay `current` trên Pi. Kiểm tra cùng ảnh với bản FP32, xác nhận các quyết định không xấu đi và đo tốc độ trực tiếp trên Pi trước khi đưa vào production.

