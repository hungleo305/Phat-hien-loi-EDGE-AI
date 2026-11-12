# Sơ đồ kiến trúc và lưu đồ thuật toán trong báo cáo

Thư mục này lưu trữ các sơ đồ nguyên lý, kiến trúc và lưu đồ thuật toán chính được sử dụng trong báo cáo đồ án tốt nghiệp. Mỗi sơ đồ đều có tệp ảnh `.png` (đúng bản nhúng trong báo cáo Word) đi kèm tệp nguồn `.drawio` hoặc `.svg` để chỉnh sửa khi cần.

| Tên tệp | Hình tương ứng trong báo cáo | Nội dung thể hiện | Định dạng nguồn |
|---|---|---|---|
| [`so_sanh_cloud_edge.png`](so_sanh_cloud_edge.png) | **Hình 1.3** | So sánh kiến trúc xử lý tập trung trên đám mây (Cloud AI) và xử lý trực tiếp tại biên (Edge AI) | [`.svg`](so_sanh_cloud_edge.svg) |
| [`dau_noi_va_nguon.png`](dau_noi_va_nguon.png) | **Hình 3.1** | Sơ đồ phân phối nguồn (nhánh 24 V DC, hạ áp 5 V, nguồn riêng 5,1 V cho Pi 4) và bảng kết nối chân GPIO/UART2 | [`.svg`](dau_noi_va_nguon.svg) |
| [`pipeline_ai_chi_tiet.png`](pipeline_ai_chi_tiet.png) | **Hình 3.7** | Lưu đồ quyết định kiểm định hộp và tem theo cơ chế kết luận sớm (Tầng 1 toàn hộp -> Tầng 3 kiểm định tem -> Tầng 2 lỗi bề mặt) | [`.drawio`](pipeline_ai_chi_tiet.drawio) |
| [`kiem_dinh_tem_chi_tiet.png`](kiem_dinh_tem_chi_tiet.png) | **Hình 3.9** | Lưu đồ chi tiết quy trình kiểm định tem nhãn (định vị ORB + Homography USAC_MAGSAC, kiểm tra chất lượng ảnh, đối chiếu 6 vùng NCC và kiểm tra hư hại) | [`.drawio`](kiem_dinh_tem_chi_tiet.drawio) |
| [`esp32_chu_trinh_mot_hop.png`](esp32_chu_trinh_mot_hop.png) | **Hình 3.16** | Lưu đồ chu trình điều khiển và phân loại một hộp trên ESP32 (cảm biến chụp, hàng đợi FIFO, nhận `RESULT` và gạt hộp lỗi tại cửa phân loại) | [`.drawio`](esp32_chu_trinh_mot_hop.drawio) |
