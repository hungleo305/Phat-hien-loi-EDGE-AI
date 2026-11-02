# THƯ MỤC 01: HUẤN LUYỆN MÔ HÌNH AI (TRAINING)

> **Ánh xạ thuyết minh đồ án:** Mục 3.2.3.1 (Chuẩn bị và phân chia dữ liệu) và Mục 3.2.3.2 (Cấu hình huấn luyện và hội tụ hàm mất mát).

---

## 1. Danh sách các tệp trong thư mục

| Tên tệp | Vai trò |
|---|---|
| **`train.py`** | Script Python huấn luyện mô hình **Tầng 1 (Toàn hộp - whole_balanced)** bằng thư viện Ultralytics YOLOv8n (ảnh $640 \times 640$, batch 4, epochs 25, tối ưu hóa AdamW). |
| **`train_surface.py`** | Script huấn luyện **Tầng 2 (Ngoại quan cục bộ - surface_finetune)** chuyên sâu cho vết rách, xước nhỏ (ảnh $960 \times 960$, batch 2). |
| **`data.yaml`** | Tệp cấu hình đường dẫn tới tập dữ liệu Train/Val/Test và định nghĩa danh sách các lớp: `['DEFECT', 'PASS', 'visible_defect']`. |
| **`best.pt`** | **Bộ não AI ban đầu** (Trọng số PyTorch Tầng 1 sau khi huấn luyện, dung lượng ~6.2 MB cho kiến trúc YOLOv8n). |
| **`best_surface.pt`** | Trọng số PyTorch Tầng 2 chuyên bắt lỗi ngoại quan (dung lượng ~6.3 MB). |
| **`evaluate.py`** | Script đánh giá độc lập mô hình trên tập kiểm thử (Test set) và tập khóa kiểm định mù BOX06 / PASS. |
| **`results.png`** | Biểu đồ biến thiên hàm mất mát ($\mathcal{L}_{CIoU}, \mathcal{L}_{DFL}, \mathcal{L}_{BCE}$) và chỉ số $mAP_{50}$ qua các epoch (minh chứng cho Báo cáo). |
| **`confusion_matrix_normalized.png`** | Ma trận nhầm lẫn chuẩn hóa chứng minh khả năng phân loại chính xác giữa PASS và DEFECT. |

---

## 2. Lệnh chạy huấn luyện lại mô hình

```bash
# Huấn luyện mô hình Tầng 1 (Toàn hộp)
python train.py

# Huấn luyện mô hình Tầng 2 (Ngoại quan bề mặt)
python train_surface.py

# Đánh giá kiểm thử
python evaluate.py
```

