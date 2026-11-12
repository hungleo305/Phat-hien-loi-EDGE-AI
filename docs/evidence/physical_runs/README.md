# Hồ sơ [4] — Kết quả chạy thử nghiệm nhận diện và phân loại hộp trên băng tải thực tế

Thư mục này lưu trữ nhật ký kết quả của **3 đợt chạy thử nghiệm liên hoàn trên mô hình băng tải thật** (trình bày tại mục `3.5.3`, `Bảng 3.10`, `Bảng 3.11` và `Phụ lục A`, `Bảng A.1` trong báo cáo).

---

## 1. Điều kiện vận hành trên mô hình thực tế

- **Ngày thực hiện**: `11/11/2026`.
- **Cấu hình vận hành chuẩn**: Đèn buồng chụp `LIGHT = 70/255`, động cơ băng tải `SPEED (PWM) = 180/255`, góc gạt servo `SERVO_ANGLE = 60°`, thời gian giữ gạt `SERVO_HOLD = 350 ms`, độ phơi sáng camera `exposure_time_absolute = 1100`, chế độ phân loại `SORT` (gạt hộp lỗi).

---

## 2. Bảng tổng hợp 3 đợt chạy thử (`summary.csv` — `Bảng 3.10`)

| Đợt chạy thử | Tệp nhật ký gốc | Tổng số lượt hộp | Số lượt `PASS` | Số lượt `DEFECT` | Số lượt `ERROR` | Nhận diện & phân loại đúng | Thời gian trung bình từ yêu cầu chụp đến có kết quả (`ms`) |
|---|---|---:|---:|---:|---:|---:|---:|
| **Đợt #4** | [`trial4.json`](trial4.json) | 28 | 7 | 21 | 0 | **28 / 28** | `1573,9` |
| **Đợt #5 (chạy lại)** | [`trial5_repeat.json`](trial5_repeat.json) | 28 | 7 | 21 | 0 | **28 / 28** | `1601,8` |
| **Đợt #6** | [`trial6.json`](trial6.json) | 30 | 7 | 23 | 0 | **30 / 30** | `1423,9` |
| **Tổng cộng** | [`summary.csv`](summary.csv) | **86** | **21** | **65** | **0** | **86 / 86 (100%)** | — |

---

## 3. Trích lục 6 lượt kiểm định trong Đợt #6 (`Bảng A.1` — Phụ lục A)

Bảng dưới đây trích 6 lượt kiểm định tiêu biểu từ tệp [`trial6.json`](trial6.json) (gồm 3 hộp lỗi và 3 hộp đạt) để minh họa cấu trúc bản ghi thời gian của trạm:

| Mã hộp (`box_id`) | Kết quả (`decision`) | Thu ảnh camera (`capture_ms`) | Xử lý AI (`ai_ms`) | Từ lúc yêu cầu chụp đến khi có kết quả (`request_to_result_ms`) |
|---:|---|---:|---:|---:|
| `152` | `DEFECT` | `95,0` | `1693,3` | `1806,1` |
| `153` | `DEFECT` | `100,0` | `800,9` | `1320,6` |
| `154` | `DEFECT` | `119,3` | `761,9` | `890,2` |
| `179` | `PASS` | `100,6` | `1864,0` | `2363,7` |
| `180` | `PASS` | `118,5` | `1863,8` | `1990,1` |
| `181` | `PASS` | `99,1` | `1723,0` | `2113,9` |

*Ghi chú*: Giá trị `request_to_result_ms` được tính từ thời điểm trạm nhận yêu cầu chụp (`CAPTURE`) cho tới khi gửi xong bản tin `RESULT`, bao gồm cả thời gian thu ảnh, xử lý AI và điều phối luồng.
