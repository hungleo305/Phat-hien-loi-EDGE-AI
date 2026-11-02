# THƯ MỤC 05: GIAO DIỆN GIÁM SÁT SCADA (DASHBOARD)

> **Ánh xạ thuyết minh đồ án:** Mục 3.4 (Cấu hình giao diện Dashboard giám sát SCADA).

---

## 1. Danh sách các tệp trong thư mục

| Tên tệp | Vai trò |
|---|---|
| **`server.py`** | **Máy chủ Web HTTP đa luồng (`ThreadingHTTPServer`):** Cung cấp các REST API thời gian thực (`/api/state`, `/api/runs`, `/api/command`) và luồng video trực tiếp MJPEG `/stream` từ camera (20 FPS). |
| **`index.html`** *(hoặc `dashboard.html`)* | **Giao diện người dùng HMI SCADA:** Hiển thị khung video camera kép (Dual-view), sơ đồ trạng thái băng tải 3 bước, khối chỉ số KPI, ô nhập tên phiên kiểm thử mới (`Named Runs`) và bảng lịch sử phân loại. |
| **`app.js`** *(hoặc `dashboard.js`)* | **Mã nguồn tương tác giao diện (Vanilla JavaScript):** Thực hiện cơ chế bất đồng bộ `fetch()`, cập nhật DOM trực tiếp 200 ms/lần không reload trang, xử lý nút nhấn điều khiển (START, STOP, DRY RUN, SORT TEST, Tải CSV/JSON). |
| **`dashboard.css`** | **Hệ thống thiết kế giao diện SCADA:** Màu nền tối chống mỏi mắt (`#0f172a`), phân biệt rõ nét trạng thái xanh lá ĐẠT (`#16a34a`) và đỏ LỖI (`#dc2626`). |

---

## 2. Các tính năng nổi bật trên giao diện Dashboard

1. **Khóa an toàn vận hành:** Bắt buộc người vận hành phải nhập tên phiên kiểm thử (ví dụ: `Kiem_thu_lo_01`) trước khi bấm `BẮT ĐẦU` (START).
2. **Quản lý lịch sử theo phiên (Named Runs):** Cho phép xem lại lịch sử và xuất file báo cáo **CSV** / **JSON** riêng biệt cho từng mẻ hàng.
3. **Modal hiệu chuẩn phần cứng trực tiếp:** Cung cấp thanh trượt điều chỉnh tốc độ động cơ PWM, góc servo ($0^\circ \text{–} 180^\circ$), thời gian giữ servo và mức sáng LED PWM ngay trên giao diện web.

---

## 3. Cách mở Dashboard

- **Trên Laptop:** Nhấp đúp vào shortcut **`MO_DASHBOARD_DATN.lnk`** ở thư mục gốc `F:\DATN\`.
- **Trình duyệt tự động mở tại:** `http://127.0.0.1:8769/`

