# Runtime AI production

Gói kiểm định ảnh được đồng bộ từ `/home/cmh/Pi4_EdgeAI/current/runtime`. Hai model NCNN FP32 giữ đầu vào toàn hộp 640 và bề mặt 960; checkpoint PyTorch cùng nguồn được giữ để xuất/đối chiếu.

| Thành phần | Vai trò |
|---|---|
| `src/current_pipeline.py` | Luồng kết luận sớm: toàn hộp → tem → bề mặt khi cần |
| `src/label_verifier.py`, `label_integrity.py` | Kiểm tra tem ORB/Homography/NCC và hư hại |
| `src/guard_logic.py` | Điều kiện bổ sung theo vùng hộp và cấu hình chụp |
| `config/app.json` | Tham số suy luận và xử lý REVIEW |
| `models/`, `assets/` | Model và tem tham chiếu |
| `samples/`, `self_check.py` | 5 ảnh hồi quy nhỏ |
| `manifest.json`, `integrity.py` | Kiểm tra nguyên vẹn SHA-256 |

Từ thư mục này: `python self_check.py --backend ncnn`.

Kết quả AI gồm PASS, DEFECT và REVIEW; trạm chuyển REVIEW thành ERROR, không tự PASS. Ảnh `samples/review.jpg` giữ tên lịch sử nhưng nhãn đối chiếu hiện tại là PASS theo xác nhận lại, như khai báo trong self-check. Tên tệp không phải nhãn thật.

Các kiểm tra bổ sung được phát triển theo bộ hộp, vị trí và ánh sáng đã ghi nhận; cần thử lại với hộp hoặc điều kiện chụp mới. Self-check 5 ảnh và hồi quy 466 ảnh không thay thế nghiệm thu vận hành độc lập.
