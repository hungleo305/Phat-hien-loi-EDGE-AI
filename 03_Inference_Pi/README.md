# Suy luận ảnh trên Raspberry Pi

`runtime/` là bản AI chuẩn của kho, đồng bộ từ production Pi: hai model NCNN FP32, checkpoint PyTorch tương ứng, ảnh tem mẫu, cấu hình, mã kiểm định và 5 ảnh self-check. `camera_profile.json` là profile camera Pi, đặt cạnh runtime theo cách station tìm cấu hình.

## Đọc mã theo thứ tự

1. `runtime/config/app.json`: kích thước ảnh, ngưỡng và chính sách REVIEW → ERROR.
2. `runtime/src/current_pipeline.py`: toàn hộp 640 → kiểm định tem → bề mặt 960 khi cần.
3. `runtime/src/base_pipeline.py`: nạp model, gọi suy luận và biểu diễn kết quả.
4. `runtime/src/label_verifier.py`, `label_integrity.py`: định vị, căn chỉnh và đối chiếu tem.
5. `runtime/src/guard_logic.py`: các điều kiện kiểm tra bổ sung theo cấu hình chụp.
6. `runtime/src/pi_camera.py`, `camera_controls.py`: camera UVC và thông số V4L2.

Không có bản “trình bày” Python/model thứ hai tại gốc module. Khi giải thích thuật toán, đọc trực tiếp runtime.

## Kiểm tra và chạy trạm

Từ gốc kho:

```bash
python 03_Inference_Pi/runtime/self_check.py --backend ncnn
python 03_Inference_Pi/run_station.py --headless --dashboard --dashboard-local-trust
```

Lệnh thứ hai dành cho Pi có camera và UART phù hợp; wrapper truyền đúng runtime của kho cho `../05_Dashboard/station/run_station.py`. Chỉ chạy một trạm giữ camera/UART. Lệnh không tự thay systemd hoặc triển khai production.

`manifest.json` bảo vệ nội dung runtime bằng SHA-256. Script [tools/verify_repository.py](../tools/verify_repository.py) kiểm tra manifest trước khi chạy AI. Model, ngưỡng và camera profile không được thay chỉ để thu gọn thư mục. [Hồ sơ hồi quy](../docs/evidence/pi466/README.md) giải thích bộ 466 ảnh và giới hạn đánh giá.
