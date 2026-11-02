"""Verify an explicitly approved printed label using alignment and local content.

This is a visual reference check, not OCR and not a probability of correctness.
The engineering cutoffs require validation with real camera positives/negatives.
"""
from pathlib import Path
import hashlib
import time

import cv2
import numpy as np
from label_integrity import LabelIntegrity


_PACKAGED_TEMPLATE=Path(__file__).resolve().parents[1]/'assets/approved_label.png'
DEFAULT_TEMPLATE=_PACKAGED_TEMPLATE if _PACKAGED_TEMPLATE.is_file() else Path(r'F:\DATN\Tai_nguyen\Label_Printing_Backup\logo3x3.png')


class LabelVerifier:
    # Coordinates refer to the approved 1200x1200 artwork, normalized to its size.
    REGIONS={
        'logo':(.06,.055,.25,.25),
        'school':(.31,.075,.92,.265),
        'project':(.045,.435,.94,.525),
        'inspector':(.045,.62,.70,.69),
        'qc':(.06,.82,.41,.895),
        'year':(.50,.84,.64,.90),
    }

    def __init__(self,template=DEFAULT_TEMPLATE,size=320,query_size=640,nfeatures=1800):
        self.template_path=Path(template).resolve()
        source=cv2.imread(str(self.template_path))
        if source is None:raise FileNotFoundError(f'Cannot read approved label: {self.template_path}')
        self.template_sha256=hashlib.sha256(self.template_path.read_bytes()).hexdigest()
        self.size=size
        self.query_size=query_size
        self.reference_cache={}
        self.reference=cv2.resize(source,(size,size),interpolation=cv2.INTER_AREA)
        self.integrity=LabelIntegrity(self.reference,self.template_path)
        self.reference_gray=self._gray(self.reference)
        self.orb=cv2.ORB_create(nfeatures=nfeatures,scaleFactor=1.15,nlevels=8,
                               edgeThreshold=12,patchSize=25,fastThreshold=9)
        self.keypoints,self.descriptors=self.orb.detectAndCompute(self.reference_gray,None)
        if self.descriptors is None or len(self.keypoints)<30:
            raise ValueError('Approved label has insufficient visual features')
        self.matcher=cv2.BFMatcher(cv2.NORM_HAMMING)
        self.reference_edges=cv2.Canny(self.reference_gray,55,140)

    @staticmethod
    def _gray(image):
        gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY) if image.ndim==3 else image
        gray=cv2.GaussianBlur(gray,(3,3),0)
        low,high=np.percentile(gray,(3,90))
        return np.clip((gray.astype(np.float32)-low)*255/max(20.,high-low),0,255).astype(np.uint8)

    def verify(self,bgr):
        start=time.perf_counter()
        result={'status':'not_found','verified':False,'template_sha256':self.template_sha256,
                'method':'ORB_MAGSAC_content_integrity_fields_v2','calibrated':False}
        def finish(status,reason):
            result.update(status=status,verified=status=='verified',reason=reason,
                          elapsed_ms=(time.perf_counter()-start)*1000)
            return result
        if bgr is None or bgr.size==0:return finish('insufficient_detail','empty crop')
        height,width=bgr.shape[:2]
        scale=min(2.,self.query_size/max(height,width))
        image=cv2.resize(bgr,(max(1,round(width*scale)),max(1,round(height*scale))))
        gray=self._gray(image)
        keypoints,descriptors=self.orb.detectAndCompute(gray,None)
        if descriptors is None:return finish('not_found','no label features')
        pairs=self.matcher.knnMatch(self.descriptors,descriptors,k=2)
        candidates=[pair[0] for pair in pairs if len(pair)==2 and pair[0].distance<.74*pair[1].distance]
        # Repeated text may send several reference points to one query point.
        unique={}
        for match in sorted(candidates,key=lambda match:match.distance):
            unique.setdefault(match.trainIdx,match)
        good=list(unique.values());result['matches']=len(good)
        if len(good)<12:return finish('not_found','approved label not localized')
        source=np.float32([self.keypoints[match.queryIdx].pt for match in good])
        target=np.float32([keypoints[match.trainIdx].pt for match in good])
        # RANSAC's minimal samples sometimes align only a text cluster on a
        # genuine printed label. On the observed stationary PASS this made
        # distributed-support validation fail intermittently despite hundreds
        # of matches. MAGSAC fits the same matches robustly; the coverage,
        # projection and every local content gate below remain mandatory.
        homography,inlier_mask=cv2.findHomography(source,target,cv2.USAC_MAGSAC,3.,maxIters=5000,confidence=.999)
        if homography is None:return finish('not_found','alignment failed')
        inliers=inlier_mask.ravel().astype(bool);inlier_count=int(inliers.sum())
        result.update(inliers=inlier_count,inlier_fraction=float(inliers.mean()))
        coverage=cv2.contourArea(cv2.convexHull(source[inliers]))/(self.size*self.size) if inlier_count>=3 else 0.
        result['reference_feature_coverage']=float(coverage)
        if inlier_count<10 or inliers.mean()<.40 or coverage<.18:
            return finish('not_found','insufficient distributed identity matches')
        corners=np.float32([[0,0],[self.size-1,0],[self.size-1,self.size-1],[0,self.size-1]])
        projected=cv2.perspectiveTransform(corners.reshape(1,4,2),homography)[0]
        area=abs(cv2.contourArea(projected));sides=np.linalg.norm(projected-np.roll(projected,1,axis=0),axis=1)
        if (not np.isfinite(projected).all() or not cv2.isContourConvex(projected.astype(np.float32))
                or area<.03*gray.size or area>1.25*gray.size or sides.max()/max(1.,sides.min())>3.):
            return finish('not_found','implausible label projection')
        result['label_corners_in_crop']=(projected/scale).tolist()
        result['min_label_side_pixels']=float(sides.min()/scale)
        if sides.min()/scale<90:
            return finish('insufficient_detail','label too small for content verification')
        aligned=cv2.warpPerspective(image,np.linalg.inv(homography),(self.size,self.size),
                                    flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT,borderValue=(255,255,255))
        valid=cv2.warpPerspective(np.ones(gray.shape,dtype=np.uint8),np.linalg.inv(homography),
                                  (self.size,self.size),flags=cv2.INTER_NEAREST)
        if float(valid.mean())<.96:return finish('insufficient_detail','label clipped by image boundary')
        aligned_gray=self._gray(aligned)
        result['sharpness']=float(cv2.Laplacian(aligned_gray,cv2.CV_32F).var())
        if result['sharpness']<35:return finish('insufficient_detail','label blurred')
        # Compare the artwork at the effective camera resolution. Fine crest
        # details in a 1200px source cannot be demanded from a 180px print ROI.
        native=max(90,min(self.size,round(sides.min()/scale)))
        cached=self.reference_cache.get(native)
        if cached is None:
            comparable=cv2.resize(self.reference,(native,native),interpolation=cv2.INTER_AREA)
            comparable=cv2.resize(comparable,(self.size,self.size),interpolation=cv2.INTER_LINEAR)
            comparable_gray=self._gray(comparable)
            reference_edges=cv2.Canny(comparable_gray,55,140)
            distance_to_reference=cv2.distanceTransform(255-reference_edges,cv2.DIST_L2,3)
            cached=(comparable_gray,reference_edges,distance_to_reference)
            if len(self.reference_cache)>=8:self.reference_cache.pop(next(iter(self.reference_cache)))
            self.reference_cache[native]=cached
        comparable_gray,reference_edges,distance_to_reference=cached
        observed_edges=cv2.Canny(aligned_gray,55,140)
        distance_to_observed=cv2.distanceTransform(255-observed_edges,cv2.DIST_L2,3)
        regions={};failed=[]
        for name,bounds in self.REGIONS.items():
            x1,y1,x2,y2=[round(value*self.size) for value in bounds]
            expected=reference_edges[y1:y2,x1:x2]>0
            observed=observed_edges[y1:y2,x1:x2]>0
            recall=float((distance_to_observed[y1:y2,x1:x2][expected]<=2.).mean()) if expected.any() else 0.
            precision=float((distance_to_reference[y1:y2,x1:x2][observed]<=2.).mean()) if observed.any() else 0.
            tile_recalls=[]
            for col in range(3):
                left=x1+(x2-x1)*col//3;right=x1+(x2-x1)*(col+1)//3
                tile=reference_edges[y1:y2,left:right]>0
                if tile.sum()>=18:
                    tile_recalls.append(float((distance_to_observed[y1:y2,left:right][tile]<=2.).mean()))
            lowest=min(tile_recalls,default=0.)
            reference_patch=comparable_gray[y1:y2,x1:x2]
            margin=2
            search=aligned_gray[max(0,y1-margin):min(self.size,y2+margin),max(0,x1-margin):min(self.size,x2+margin)]
            correlation=float(cv2.matchTemplate(search,reference_patch,cv2.TM_CCOEFF_NORMED).max())
            coarse_reference=cv2.GaussianBlur(reference_patch,(7,7),2.)
            coarse_search=cv2.GaussianBlur(search,(7,7),2.)
            coarse_correlation=float(cv2.matchTemplate(coarse_search,coarse_reference,cv2.TM_CCOEFF_NORMED).max())
            regions[name]={'edge_recall':recall,'edge_precision':precision,
                           'minimum_tile_recall':lowest,'correlation':correlation,
                           'coarse_correlation':coarse_correlation}
            if name=='logo':
                # Fine crest strokes disappear in small printed-camera ROIs;
                # require coherent coarse appearance rather than each stroke.
                accepted=correlation>=.72 and coarse_correlation>=.78
            else:
                accepted=recall>=.58 and precision>=.50 and lowest>=.35 and correlation>=.65
            if not accepted:failed.append(name)
        result.update(regions=regions,failed_regions=failed)
        integrity=self.integrity.check(aligned,aligned_gray,comparable_gray,native)
        result['integrity']=integrity
        if not integrity['passed']:return finish('mismatch','; '.join(integrity['reasons']))
        if failed:return finish('mismatch','label content differs in '+', '.join(failed))
        return finish('verified','approved identity, QC/year and visible label integrity matched')
