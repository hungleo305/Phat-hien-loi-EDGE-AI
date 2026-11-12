# Huấn luyện và đánh giá mô hình

Hai mô hình YOLOv8n có vai trò khác nhau: toàn hộp 640 nhận PASS/DEFECT; bề mặt 960 tìm vùng `visible_defect`. Bộ kiểm định tem dùng ảnh mẫu và OpenCV, không huấn luyện bằng hai script này.

| Tệp | Công việc |
|---|---|
| `train.py` | Huấn luyện toàn hộp hoặc chọn `--model surface` |
| `train_surface.py` | Điểm chạy gọn cho mô hình bề mặt, dùng chung code `train.py` |
| `evaluate.py` | Đo Precision, Recall, mAP của riêng detector |
| `data.yaml` | Cấu hình bộ toàn hộp trên laptop hiện tại |
| `results.png`, `confusion_matrix_normalized.png` | Hình minh họa giai đoạn huấn luyện; số liệu và nguồn tại docs/evidence/training_data |

Checkpoint cuối được lưu duy nhất tại `../03_Inference_Pi/runtime/models/whole_balanced.pt` và `surface_finetuned.pt`.

## Dữ liệu và môi trường

Laptop hiện tại giữ bộ dữ liệu tại `F:/DATN/Du_lieu_goc/Huan_luyen/`: `dataset_detection_balanced` cho toàn hộp, `dataset_surface_combined` cho bề mặt, `initial_weights` cho hai checkpoint khởi tạo. Ảnh và nhãn không nằm trong Git. Với máy khác, truyền `--data` và `--weights` trỏ tới dữ liệu/checkpoint đã chuẩn bị.

Chạy từ gốc kho bằng môi trường PyTorch/Ultralytics. Dùng `--device 0` cho CUDA hoặc `--device cpu`; không có bước tự tải checkpoint thay thế.

```powershell
python 01_Training/train.py --output F:/DATN/Cong_cu_phat_trien/outputs/train_whole_moi
python 01_Training/train_surface.py --output F:/DATN/Cong_cu_phat_trien/outputs/train_surface_moi
python 01_Training/evaluate.py --model whole --output F:/DATN/Cong_cu_phat_trien/outputs/eval_whole_moi
python 01_Training/evaluate.py --model surface --output F:/DATN/Cong_cu_phat_trien/outputs/eval_surface_moi
```

Đường dẫn đầu ra phải chưa tồn tại; các lệnh tạo kết quả mới và không thay model production. Mặc định đánh giá toàn hộp trên `test`, bề mặt trên `val`, đúng loại tập đo trong báo cáo. Có thể truyền `--split` khi có mục đích đánh giá khác.

Toàn hộp dùng 205 ảnh nguồn, lặp 50 ảnh PASS thành 150 lượt PASS để cân bằng với 155 lượt DEFECT. Bề mặt dùng 559 ảnh; bộ bổ sung cũ đã được đưa vào huấn luyện nên không còn là kiểm thử độc lập. [Thông số và chỉ số gốc](../docs/evidence/training_data/README.md) ghi rõ nguồn, tập đo và giới hạn. Chạy lại cùng seed chưa bảo đảm kết quả số học giống tuyệt đối giữa mọi phiên bản thư viện/phần cứng.
