"""
=============================================================================
ĐỒ ÁN TỐT NGHIỆP KỸ SƯ - HỌC VIỆN KỸ THUẬT MẬT MÃ
CHUYÊN NGÀNH: AN TOÀN THÔNG TIN / HỆ THỐNG NHÚNG & EDGE AI
SINH VIÊN THỰC HIỆN: CHU MẠNH HÙNG

MÃ NGUỒN: 03_Inference_Pi/template_matching.py
CHỨC NĂNG: KIỂM ĐỊNH TÍNH TOÀN VẸN CỦA TEM NHÃN BẰNG HOMOGRAPHY VÀ ĐỐI SÁNH CỤC BỘ
THAM CHIẾU BÁO CÁO: MỤC 3.2.4 - PHƯƠNG PHÁP ĐỐI SÁNH MẪU VÀ XỬ LÝ ẢNH TRUYỀN THỐNG
=============================================================================

1. NGUYÊN LÝ HOẠT ĐỘNG:
   - Thay vì dùng OCR cồng kềnh (Tesseract OCR quá nặng và chậm trên Pi 4, ~1.8s/ảnh),
     hệ thống sử dụng kỹ thuật thị giác máy tính truyền thống kết hợp biến đổi hình học:
     + Trích xuất đặc trưng điểm ORB (Oriented FAST and Rotated BRIEF).
     + Ước lượng ma trận Homography 3x3 bằng thuật toán USAC_MAGSAC siêu bền vững.
     + Biến đổi phối cảnh (Perspective Warp) đưa tem nhãn về ảnh chuẩn phẳng 320x320.
     + Phân tích đa tiêu chí trên 6 phân vùng chức năng: Logo KMA, Tên trường,
       Đề tài, Cán bộ kiểm định, Trạng thái QC ('PASSED'/'FAILED'), và Năm ('2026'/'2025').

2. TOÁN HỌC ÁP DỤNG:
   - Biến đổi Homography phẳng:
       [x']       [h11  h12  h13]   [x]
       [y']  =  H [h21  h22  h23] * [y]
       [ 1]       [h31  h32  h33]   [1]
   - Hệ số tương quan chéo chuẩn hóa (Normalized Cross-Correlation - NCC):
       R(x, y) = \frac{\sum_{x',y'} (T'(x',y') \cdot I'(x+x', y+y'))}{\sqrt{\sum_{x',y'} T'(x',y')^2 \cdot \sum_{x',y'} I'(x+x', y+y')^2}}
   - Đánh giá biên cạnh Chamfer: Khoảng cách L2 Distance Transform giữa biên Canny thực tế và lý thuyết.
"""

from pathlib import Path
import hashlib
import time

import cv2
import numpy as np
from label_integrity import LabelIntegrity

# Đường dẫn ảnh mẫu chuẩn đã được duyệt (Approved Reference Label)
_PACKAGED_TEMPLATE = Path(__file__).resolve().parents[1] / 'assets/approved_label.png'
DEFAULT_TEMPLATE = _PACKAGED_TEMPLATE if _PACKAGED_TEMPLATE.is_file() else Path(r'F:\DATN\Tai_nguyen\Label_Printing_Backup\logo3x3.png')


class LabelVerifier:
    """
    Bộ kiểm định tính hợp lệ và toàn vẹn của tem nhãn dán trên vỏ hộp carton.
    Tọa độ chuẩn hóa [x1, y1, x2, y2] chia theo tỷ lệ của bản thiết kế 1200x1200.
    """
    REGIONS = {
        'logo': (.06, .055, .25, .25),        # Biểu trưng Học viện Kỹ thuật Mật mã
        'school': (.31, .075, .92, .265),     # Dòng chữ "HỌC VIỆN KỸ THUẬT MẬT MÃ"
        'project': (.045, .435, .94, .525),   # Dòng chữ "ĐỒ ÁN TỐT NGHIỆP KỸ SƯ"
        'inspector': (.045, .62, .70, .69),   # "CB Kiểm định: Chu Mạnh Hùng"
        'qc': (.06, .82, .41, .895),          # Dấu "QC PASSED" hoặc "QC FAILED"
        'year': (.50, .84, .64, .90),         # Năm kiểm định "2026" (hoặc giả mạo "2025")
    }

    def __init__(self, template=DEFAULT_TEMPLATE, size=320, query_size=640, nfeatures=1800):
        """
        Khởi tạo bộ kiểm định tem:
        - template: Đường dẫn tới file ảnh mẫu chuẩn.
        - size: Kích thước chuẩn hóa sau khi nắn góc phối cảnh (mặc định 320x320 px).
        - query_size: Độ phân giải tối đa khi trích xuất đặc trưng điểm (640 px).
        - nfeatures: Số lượng điểm đặc trưng ORB tối đa (1800 điểm).
        """
        self.template_path = Path(template).resolve()
        source = cv2.imread(str(self.template_path))
        if source is None:
            raise FileNotFoundError(f'Không thể đọc file ảnh tem mẫu chuẩn: {self.template_path}')
        
        # Khóa băm SHA-256 để kiểm soát phiên bản và tính toàn vẹn mẫu tem
        self.template_sha256 = hashlib.sha256(self.template_path.read_bytes()).hexdigest()
        self.size = size
        self.query_size = query_size
        self.reference_cache = {}
        
        # Chuẩn hóa ảnh mẫu về kích thước 320x320
        self.reference = cv2.resize(source, (size, size), interpolation=cv2.INTER_AREA)
        # Bộ kiểm tra tính nguyên vẹn vật lý (chống rách, bôi bẩn, lộ phôi carton)
        self.integrity = LabelIntegrity(self.reference, self.template_path)
        self.reference_gray = self._gray(self.reference)
        
        # Khởi tạo bộ trích xuất đặc trưng ORB (tối ưu hóa cho CPU ARM Pi 4)
        self.orb = cv2.ORB_create(
            nfeatures=nfeatures,
            scaleFactor=1.15,
            nlevels=8,
            edgeThreshold=12,
            patchSize=25,
            fastThreshold=9
        )
        self.keypoints, self.descriptors = self.orb.detectAndCompute(self.reference_gray, None)
        if self.descriptors is None or len(self.keypoints) < 30:
            raise ValueError('Ảnh mẫu chuẩn không đủ số lượng điểm đặc trưng thị giác!')
            
        # Bộ so khớp khoảng cách Hamming (Brute-Force Matcher) cho descriptor nhị phân của ORB
        self.matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
        # Bản đồ biên cạnh Canny của mẫu chuẩn
        self.reference_edges = cv2.Canny(self.reference_gray, 55, 140)

    @staticmethod
    def _gray(image):
        """
        Tiền xử lý ảnh xám và cân bằng độ tương phản cục bộ:
        1. Chuyển đổi không gian màu BGR sang Grayscale.
        2. Lọc mờ Gaussian làm mịn nhiễu sensor camera.
        3. Cắt phân vị 3%-90% để khử ảnh hưởng của chóa sáng đèn LED công nghiệp.
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        low, high = np.percentile(gray, (3, 90))
        return np.clip((gray.astype(np.float32) - low) * 255 / max(20., high - low), 0, 255).astype(np.uint8)

    def verify(self, bgr):
        """
        Quy trình kiểm định tem nhãn trên ảnh thực tế:
        Bước 1: Trích xuất đặc trưng ORB và so khớp tỉ lệ khoảng cách (Lowe's ratio test < 0.74).
        Bước 2: Tìm ma trận Homography bằng USAC_MAGSAC; kiểm tra tính lồi và tỉ lệ co giãn.
        Bước 3: Biến đổi phối cảnh ngược đưa tem về ảnh chuẩn 320x320 phẳng.
        Bước 4: Kiểm tra độ sắc nét (Laplacian variance >= 35).
        Bước 5: So khớp từng phân vùng bằng tương quan chéo NCC và biên cạnh Canny Chamfer.
        Bước 6: Kiểm tra tính toàn vẹn vật lý (rách tem, mực vẽ bẩn).
        """
        start = time.perf_counter()
        result = {
            'status': 'not_found',
            'verified': False,
            'template_sha256': self.template_sha256,
            'method': 'ORB_MAGSAC_content_integrity_fields_v2',
            'calibrated': False
        }

        def finish(status, reason):
            result.update(
                status=status,
                verified=(status == 'verified'),
                reason=reason,
                elapsed_ms=(time.perf_counter() - start) * 1000
            )
            return result

        if bgr is None or bgr.size == 0:
            return finish('insufficient_detail', 'empty crop')

        # Thu phóng ảnh đầu vào về kích thước phù hợp để tối ưu tốc độ xử lý
        height, width = bgr.shape[:2]
        scale = min(2., self.query_size / max(height, width))
        image = cv2.resize(bgr, (max(1, round(width * scale)), max(1, round(height * scale))))
        gray = self._gray(image)

        # Trích xuất đặc trưng trên ảnh quan sát
        keypoints, descriptors = self.orb.detectAndCompute(gray, None)
        if descriptors is None:
            return finish('not_found', 'no label features')

        # So khớp KNN (k=2) và lọc theo điều kiện kiểm định tỉ số Lowe (Lowe's ratio test)
        pairs = self.matcher.knnMatch(self.descriptors, descriptors, k=2)
        candidates = [p[0] for p in pairs if len(p) == 2 and p[0].distance < 0.74 * p[1].distance]

        # Khử trùng lặp: Một điểm trên ảnh truy vấn chỉ tương ứng với một điểm tốt nhất trên mẫu
        unique = {}
        for match in sorted(candidates, key=lambda m: m.distance):
            unique.setdefault(match.trainIdx, match)
        good = list(unique.values())
        result['matches'] = len(good)

        # Cần tối thiểu 12 điểm so khớp tin cậy để định vị tem
        if len(good) < 12:
            return finish('not_found', 'approved label not localized')

        source = np.float32([self.keypoints[m.queryIdx].pt for m in good])
        target = np.float32([keypoints[m.trainIdx].pt for m in good])

        # Ước lượng Homography bằng thuật toán USAC_MAGSAC (bền vững vượt trội so với RANSAC truyền thống)
        homography, inlier_mask = cv2.findHomography(source, target, cv2.USAC_MAGSAC, 3.0, maxIters=5000, confidence=0.999)
        if homography is None:
            return finish('not_found', 'alignment failed')

        inliers = inlier_mask.ravel().astype(bool)
        inlier_count = int(inliers.sum())
        result.update(inliers=inlier_count, inlier_fraction=float(inliers.mean()))

        # Kiểm tra độ phủ không gian của các điểm inlier (chống chụm điểm tại 1 góc chữ)
        coverage = cv2.contourArea(cv2.convexHull(source[inliers])) / (self.size * self.size) if inlier_count >= 3 else 0.0
        result['reference_feature_coverage'] = float(coverage)
        if inlier_count < 10 or inliers.mean() < 0.40 or coverage < 0.18:
            return finish('not_found', 'insufficient distributed identity matches')

        # Chiếu 4 góc của tem mẫu sang tọa độ ảnh quan sát để kiểm tra tính hợp lý hình học
        corners = np.float32([[0, 0], [self.size - 1, 0], [self.size - 1, self.size - 1], [0, self.size - 1]])
        projected = cv2.perspectiveTransform(corners.reshape(1, 4, 2), homography)[0]
        area = abs(cv2.contourArea(projected))
        sides = np.linalg.norm(projected - np.roll(projected, 1, axis=0), axis=1)

        # Điều kiện loại trừ biến dạng phi vật lý (đa giác tự cắt, diện tích quá nhỏ/lớn, méo mó quá 3 lần)
        if (not np.isfinite(projected).all() or not cv2.isContourConvex(projected.astype(np.float32))
                or area < 0.03 * gray.size or area > 1.25 * gray.size or sides.max() / max(1., sides.min()) > 3.0):
            return finish('not_found', 'implausible label projection')

        result['label_corners_in_crop'] = (projected / scale).tolist()
        result['min_label_side_pixels'] = float(sides.min() / scale)
        if sides.min() / scale < 90:
            return finish('insufficient_detail', 'label too small for content verification')

        # Biến đổi phối cảnh ngược (Warp Perspective) đưa tem về ảnh chuẩn 320x320
        aligned = cv2.warpPerspective(
            image, np.linalg.inv(homography), (self.size, self.size),
            flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255)
        )
        valid = cv2.warpPerspective(
            np.ones(gray.shape, dtype=np.uint8), np.linalg.inv(homography),
            (self.size, self.size), flags=cv2.INTER_NEAREST
        )
        if float(valid.mean()) < 0.96:
            return finish('insufficient_detail', 'label clipped by image boundary')

        aligned_gray = self._gray(aligned)
        # Đánh giá độ nét bằng phương sai toán tử Laplace
        result['sharpness'] = float(cv2.Laplacian(aligned_gray, cv2.CV_32F).var())
        if result['sharpness'] < 35:
            return finish('insufficient_detail', 'label blurred')

        # So sánh ảnh ở độ phân giải thực tế của camera (Multiscale Reference Cache)
        native = max(90, min(self.size, round(sides.min() / scale)))
        cached = self.reference_cache.get(native)
        if cached is None:
            comparable = cv2.resize(self.reference, (native, native), interpolation=cv2.INTER_AREA)
            comparable = cv2.resize(comparable, (self.size, self.size), interpolation=cv2.INTER_LINEAR)
            comparable_gray = self._gray(comparable)
            reference_edges = cv2.Canny(comparable_gray, 55, 140)
            distance_to_reference = cv2.distanceTransform(255 - reference_edges, cv2.DIST_L2, 3)
            cached = (comparable_gray, reference_edges, distance_to_reference)
            if len(self.reference_cache) >= 8:
                self.reference_cache.pop(next(iter(self.reference_cache)))
            self.reference_cache[native] = cached

        comparable_gray, reference_edges, distance_to_reference = cached
        observed_edges = cv2.Canny(aligned_gray, 55, 140)
        distance_to_observed = cv2.distanceTransform(255 - observed_edges, cv2.DIST_L2, 3)

        # Kiểm tra chi tiết từng phân vùng chức năng (6 REGIONS)
        regions = {}
        failed = []
        for name, bounds in self.REGIONS.items():
            x1, y1, x2, y2 = [round(val * self.size) for val in bounds]
            expected = reference_edges[y1:y2, x1:x2] > 0
            observed = observed_edges[y1:y2, x1:x2] > 0

            # Đo độ chính xác (Precision) và độ phủ (Recall) của biên cạnh Chamfer
            recall = float((distance_to_observed[y1:y2, x1:x2][expected] <= 2.0).mean()) if expected.any() else 0.0
            precision = float((distance_to_reference[y1:y2, x1:x2][observed] <= 2.0).mean()) if observed.any() else 0.0

            tile_recalls = []
            for col in range(3):
                left = x1 + (x2 - x1) * col // 3
                right = x1 + (x2 - x1) * (col + 1) // 3
                tile = reference_edges[y1:y2, left:right] > 0
                if tile.sum() >= 18:
                    tile_recalls.append(float((distance_to_observed[y1:y2, left:right][tile] <= 2.0).mean()))
            lowest = min(tile_recalls, default=0.0)

            # Tính hệ số tương quan chéo chuẩn hóa (NCC)
            reference_patch = comparable_gray[y1:y2, x1:x2]
            margin = 2
            search = aligned_gray[max(0, y1 - margin):min(self.size, y2 + margin), max(0, x1 - margin):min(self.size, x2 + margin)]
            correlation = float(cv2.matchTemplate(search, reference_patch, cv2.TM_CCOEFF_NORMED).max())

            # Tương quan chéo ở mức mờ hạt thô (Coarse NCC) để chống nhiễu hạt sensor
            coarse_reference = cv2.GaussianBlur(reference_patch, (7, 7), 2.0)
            coarse_search = cv2.GaussianBlur(search, (7, 7), 2.0)
            coarse_correlation = float(cv2.matchTemplate(coarse_search, coarse_reference, cv2.TM_CCOEFF_NORMED).max())

            regions[name] = {
                'edge_recall': recall,
                'edge_precision': precision,
                'minimum_tile_recall': lowest,
                'correlation': correlation,
                'coarse_correlation': coarse_correlation
            }

            if name == 'logo':
                # Biểu trưng trường yêu cầu hình dạng tổng thể nhất quán (NCC >= 0.72 & Coarse >= 0.78)
                accepted = (correlation >= 0.72 and coarse_correlation >= 0.78)
            else:
                # Các dòng chữ văn bản và trường QC/Năm yêu cầu cả biên nét và tương quan độ sáng
                accepted = (recall >= 0.58 and precision >= 0.50 and lowest >= 0.35 and correlation >= 0.65)

            if not accepted:
                failed.append(name)

        result.update(regions=regions, failed_regions=failed)

        # Kiểm tra tính toàn vẹn vật lý bề mặt tem nhãn (rách, viết đè bút bi/bút dạ)
        integrity = self.integrity.check(aligned, aligned_gray, comparable_gray, native)
        result['integrity'] = integrity

        if not integrity['passed']:
            return finish('mismatch', '; '.join(integrity['reasons']))
        if failed:
            return finish('mismatch', 'label content differs in ' + ', '.join(failed))

        # Đạt toàn bộ các điều kiện khắt khe -> XÁC NHẬN HỢP LỆ (VERIFIED)
        return finish('verified', 'approved identity, QC/year and visible label integrity matched')
