# Xuất ứng viên NCNN

Production sử dụng hai model NCNN FP32 trong `../03_Inference_Pi/runtime/models`. Thư mục này chỉ chứa công cụ xuất ứng viên; không chứa thêm bản sao model.

`export_ncnn.py` lấy đúng hai checkpoint PyTorch trong runtime, xuất NCNN FP16 vào thư mục mới và ghi SHA-256, dung lượng, marker FP16 vào `export_manifest.json`. NCNN là định dạng/thư viện suy luận; tên NCNN không đồng nghĩa với FP16.

Từ gốc kho, trong môi trường có Ultralytics và công cụ xuất NCNN:

```powershell
python 02_Optimization/export_ncnn.py --output-root F:/DATN/Cong_cu_phat_trien/work/fp16_moi
```

`export_ncnn.bat` và `export_ncnn.sh` gọi cùng script, nhận đường dẫn đầu ra làm đối số. Đầu ra phải là thư mục mới trong workspace. Không chạy xuất đè lên runtime đang dùng.

FP16 giảm dung lượng nhưng chưa làm Pi nhanh hơn trong phép so sánh đã thực hiện: FP32 trung bình 1071,8 ms, FP16 1096,0 ms trên cùng bộ hồi quy 466 ảnh. Vì vậy giữ FP32. [Bằng chứng FP16](../docs/evidence/fp16/README.md) và [thử kích thước bề mặt](../docs/evidence/surface_sizes/README.md) trình bày điều kiện đo; mỗi ứng viên mới phải kiểm tra lại kết quả và tốc độ trước khi cân nhắc triển khai.
