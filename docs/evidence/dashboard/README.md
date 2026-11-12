# Hồ sơ [2] — Giao diện Web Dashboard thực tế đang vận hành

Thư mục này lưu trữ các ảnh chụp màn hình thực tế của giao diện **Web Dashboard** khi kết nối trực tiếp với trạm **Raspberry Pi 4** và **ESP32** (trình bày tại mục `3.4`, `Hình 3.17`–`3.19` trong báo cáo).

---

## 1. Danh mục hình ảnh minh chứng

| Tên tệp ảnh | Hình trong báo cáo | Nội dung hiển thị trên giao diện |
|---|---|---|
| [`dashboard_overview.jpg`](dashboard_overview.jpg) | **Hình 3.17** | Giao diện tổng quan của Dashboard: trạng thái kết nối Pi / Camera / AI / ESP32, chỉ báo cảm biến, bộ đếm phiên chạy (`Tổng 30`, `PASS 7`, `DEFECT 23` của phiên `#6`), khung hình camera trực tiếp và ảnh kết quả kiểm định. |
| [`dashboard_settings.jpg`](dashboard_settings.jpg) | **Hình 3.18** | Cửa sổ cài đặt thông số vận hành: hiển thị đúng bộ thông số chuẩn đang áp dụng (`LIGHT = 70/255`, `SPEED = 180/255`, góc gạt `60°`, thời gian giữ gạt `350 ms`, phơi sáng camera `1100`). |
| [`dashboard_history.jpg`](dashboard_history.jpg) | **Hình 3.19** | Bảng tra cứu lịch sử các lượt kiểm định trong phiên đã lưu kèm nút xuất dữ liệu ra tệp **CSV** / **JSON**. |

---

## 2. Liên kết tới mã nguồn giao diện

- Mã nguồn giao diện và máy chủ điều phối: [`05_Dashboard/station/`](../../../05_Dashboard/station/README.md).
- Hướng dẫn vận hành giao diện: [`docs/VAN_HANH.md`](../../VAN_HANH.md).
