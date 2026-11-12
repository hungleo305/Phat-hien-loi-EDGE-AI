# Thành phần dữ liệu và kết quả huấn luyện

## Bộ V4

[v4_audit.json](v4_audit.json) ghi 295 ảnh, chia thành:

| Tập | PASS | DEFECT | Tổng ảnh |
|---|---:|---:|---:|
| Huấn luyện | 50 | 155 | 205 |
| Xác thực | 10 | 30 | 40 |
| Kiểm thử | 20 | 30 | 50 |
| Tổng | 80 | 215 | 295 |

Trong trường `class_2`, số được đếm là **vùng lỗi được gán nhãn**, không phải số ảnh. Mỗi ảnh có thể có nhiều vùng lỗi.

Mô hình toàn hộp sử dụng 205 ảnh nguồn huấn luyện. 50 ảnh PASS được dùng ba lần để cân bằng với 155 ảnh DEFECT, tạo 305 lượt ảnh trong một lần đi qua tập huấn luyện; không tạo thêm hộp hoặc ảnh nguồn.

## Bộ huấn luyện bề mặt kết hợp

[surface_combined_audit.json](surface_combined_audit.json) ghi:

| Nguồn | Tổng ảnh | Có vùng lỗi bề mặt | Không có vùng lỗi bề mặt |
|---|---:|---:|---:|
| Bộ dữ liệu giai đoạn trước | 354 | 263 | 91 |
| Huấn luyện V4 | 205 | 110 | 95 |
| Tổng huấn luyện | 559 | 373 | 186 |

354 ảnh bổ sung được gộp từ 248 ảnh train, 71 valid và 35 test của bộ trước. Chỉ nhãn vùng rách/xước/hư hại được giữ lại cho mô hình bề mặt. Ảnh không có vùng lỗi vẫn có thể sai nội dung tem. Phần xác thực riêng của mô hình bề mặt là 40 ảnh V4, không nằm trong 559 ảnh huấn luyện. Các tập của bộ trước sau khi gộp không còn là tập kiểm thử độc lập cho mô hình này.

Bộ hộp hiện hành dùng mẫu tem hiện tại. Nội dung/kiểu tem trong dữ liệu bổ sung không quy định mẫu tem hợp lệ; phần đối chiếu nội dung tem dùng ảnh tham chiếu của runtime.

## Mô hình được chọn

| Mô hình | Đầu vào | Precision | Recall | mAP@50 | mAP@50–95 | Tập đo |
|---|---|---:|---:|---:|---:|---|
| Toàn hộp | 640 × 640 | 0,650 | 0,786 | 0,726 | 0,560 | Kiểm thử V4 |
| Bề mặt | 960 × 960 | 0,398 | 0,470 | 0,391 | 0,161 | Xác thực V4 |

Xem `whole_metrics.json`, `surface_metrics.json`, `whole_args.yaml`, `surface_args.yaml`. Hai hàng dùng tập đánh giá khác nhau, không xếp hạng trực tiếp hai mô hình. Các chỉ số phát hiện vùng không đồng nghĩa với độ chính xác cuối của toàn pipeline.

SHA-256 checkpoint toàn hộp: `cee48c449020ad81f3e1bc952bf1dacd95c4d067bec1bf42fb3ca08e58c63848`; bề mặt: `4539b799ed3990c6b5554b847cdfd66be7f4fb7732ceae386a88a7f4b45ec447`. Có thể đối chiếu với [manifest runtime](../../../03_Inference_Pi/runtime/manifest.json). Không kèm toàn bộ ảnh huấn luyện trong hồ sơ này.
