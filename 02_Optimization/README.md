# THƯ MỤC 02: CHUYỂN ĐỔI & TỐI ƯU HÓA MÔ HÌNH (OPTIMIZATION)

> **Ánh xạ thuyết minh đồ án:** Mục 3.2.3.3 (Quy trình chuyển đổi và lượng tử hóa sang NCNN).

---

## 1. Danh sách các tệp trong thư mục

| Tên tệp | Vai trò |
|---|---|
| **`export_ncnn.py`** | Script Python gọi `model.export(format='ncnn', half=True)` để tự động nén trọng số từ PyTorch sang NCNN FP16. |
| **`export_ncnn.sh`** | Script Bash ghi chú 4 bước dòng lệnh kinh điển: PyTorch $\rightarrow$ ONNX $\rightarrow$ `onnx2ncnn` $\rightarrow$ `ncnnoptimize` FP16. |
| **`export_ncnn.bat`** | Script chạy chuyển đổi trên hệ điều hành Windows. |
| **`ncnn_models/tier1_whole_balanced/`** | Thư mục mô hình NCNN Tầng 1 đã tối ưu (gồm `model.ncnn.param` và `model.ncnn.bin`). |
| **`ncnn_models/tier2_surface_finetuned/`** | Thư mục mô hình NCNN Tầng 2 đã tối ưu (gồm `model.ncnn.param` và `model.ncnn.bin`). |

---

## 2. Các tệp mô hình NCNN nhị phân quan trọng

Mỗi thư mục mô hình NCNN gồm 2 tệp nhị phân cốt lõi:
1. **`model.ncnn.param`**: Tệp văn bản mô tả cấu trúc đồ thị mạng nơ-ron sau khi đã áp dụng **gộp lớp (Layer Fusion)**: hợp nhất các lớp `Convolution + BatchNormalization + SiLU` thành một khối tính toán duy nhất, triệt tiêu việc ghi đệm trung gian vào RAM.
2. **`model.ncnn.bin`**: Tệp nhị phân lưu toàn bộ trọng số (Weights & Biases) đã được **lượng tử hóa bán chính xác FP16** (16-bit Float), giảm 50% dung lượng bộ nhớ và tận dụng tối đa tập lệnh gia tốc phần cứng **ARM NEON SIMD** trên 4 nhân CPU của Raspberry Pi 4.

---

## 3. Lệnh chạy xuất mô hình

```bash
python export_ncnn.py
```
Mô hình sau khi xuất sẽ được nạp trực tiếp vào pipeline trên Pi ở thư mục `03_Inference_Pi/models/`.

