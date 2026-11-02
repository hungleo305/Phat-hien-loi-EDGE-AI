"""Aligned label checks: paper damage, added marks and fixed QC/year fields.

Uses current pixels only. Engineering limits below are not probabilities or a
guarantee about unreadable characters. Artwork variants are field references,
never additional labels accepted as whole products.
"""
from pathlib import Path
import hashlib
import cv2
import numpy as np


class LabelIntegrity:
    FIELDS={'qc':(.06,.82,.41,.895),'year':(.50,.84,.64,.90)}
    VARIANTS=(('tem_QC_FAILED_2026_cropped.png',False,True),
              ('tem_QC_FAILED_2025_cropped.png',False,False),
              ('tem_QC_PASSED_2025_cropped.png',True,False))

    def __init__(self, reference, template_path):
        self.size=reference.shape[0]
        self.prototypes=[('approved',reference,True,True)]
        self.assets={}
        for name,qc_ok,year_ok in self.VARIANTS:
            path=Path(template_path).parent/name
            if not path.is_file():
                raise FileNotFoundError('Required QC/year field reference missing: '+str(path))
            picture=cv2.imread(str(path))
            if picture is None:raise ValueError('Cannot read field reference: '+str(path))
            self.prototypes.append((name,cv2.resize(picture,(self.size,self.size),interpolation=cv2.INTER_AREA),qc_ok,year_ok))
            self.assets[name]=hashlib.sha256(path.read_bytes()).hexdigest()
        self.cache={}

    @staticmethod
    def gray(image):
        gray=cv2.GaussianBlur(cv2.cvtColor(image,cv2.COLOR_BGR2GRAY),(3,3),0)
        low,high=np.percentile(gray,(3,90))
        return np.clip((gray.astype(np.float32)-low)*255/max(20.,high-low),0,255).astype(np.uint8)

    @staticmethod
    def components(mask,min_area,min_span):
        _,_,stats,_=cv2.connectedComponentsWithStats(mask.astype(np.uint8),8)
        return [dict(x=int(x),y=int(y),width=int(w),height=int(h),area=int(a))
                for x,y,w,h,a in stats[1:] if a>=min_area and min(w,h)>=min_span]

    def check(self,aligned,aligned_gray,reference_gray,native):
        # Integral size is fixed at 320 by the verifier, independent of the
        # object's 2D contour. Smooth lighting is removed before local marks.
        n=self.size
        radius=max(1,round(n*5/320))
        minimum=cv2.erode(reference_gray,np.ones((2*radius+1,2*radius+1),np.uint8))
        observed=cv2.GaussianBlur(aligned_gray,(5,5),0)
        dark=np.maximum(0,minimum.astype(np.float32)-observed.astype(np.float32))
        paper_mask=(minimum>210).astype(np.float32)
        # Estimate shading from paper pixels only. Zero residuals on printed
        # strokes must not pull this estimate down and invent dark bands next
        # to a legitimate logo, separator or QC panel.
        sigma=n*9/320
        smooth=cv2.GaussianBlur(dark*paper_mask,(0,0),sigma)/np.maximum(
            .01,cv2.GaussianBlur(paper_mask,(0,0),sigma))
        marks=((dark-smooth)>40)&(paper_mask>0)
        margin=round(n*.075)
        marks[:margin]=False;marks[-margin:]=False
        marks[:,:margin]=False;marks[:,-margin:]=False
        added=[c for c in self.components(marks,round(n*n*100/102400),max(3,round(n*8/320)))
               if c['area']/(c['width']*c['height'])>=.28]

        # A torn corner can expose cardboard over both white paper and black
        # print, where an edge-only white-background check would be blind.
        paper=np.maximum(25,np.percentile(aligned,90,axis=(0,1)))
        balanced=np.clip(aligned.astype(np.float32)/paper*230,0,255)
        b,g,r=cv2.split(balanced)
        reference=self.prototypes[0][1].astype(np.float32)
        red=(reference[:,:,2]-reference[:,:,0])>40
        red=cv2.dilate(red.astype(np.uint8),np.ones((15,15),np.uint8))>0
        exposed=((r-b)>22)&((r-g)>6)&~red
        border=max(1,round(n*3/320))
        exposed[:border]=False;exposed[-border:]=False
        exposed[:,:border]=False;exposed[:,-border:]=False
        torn=[c for c in self.components(exposed,round(n*n*350/102400),max(4,round(n*12/320)))
              if (c['x']<n*.07 and c['x']+c['width']>n*.08) or
              (c['y']<n*.07 and c['y']+c['height']>n*.08) or
              (c['x']+c['width']>n*.93 and c['x']<n*.92) or
              (c['y']+c['height']>n*.93 and c['y']<n*.92)]

        cached=self.cache.get(native)
        if cached is None:
            cached=[]
            for name,picture,qc_ok,year_ok in self.prototypes:
                matched=cv2.resize(cv2.resize(picture,(native,native),interpolation=cv2.INTER_AREA),(n,n),interpolation=cv2.INTER_LINEAR)
                cached.append((name,self.gray(matched),qc_ok,year_ok))
            if len(self.cache)>=8:self.cache.pop(next(iter(self.cache)))
            self.cache[native]=cached
        fields={};reasons=[]
        for field,bounds in self.FIELDS.items():
            x1,y1,x2,y2=[round(v*n) for v in bounds]
            search=aligned_gray[y1-3:y2+3,x1-3:x2+3]
            scores=[]
            for name,gray,qc_ok,year_ok in cached:
                score=float(cv2.matchTemplate(search,gray[y1:y2,x1:x2],cv2.TM_CCOEFF_NORMED).max())
                scores.append((score,name,qc_ok if field=='qc' else year_ok))
            good=max((row for row in scores if row[2]),default=(0.,'',True))
            bad=max((row for row in scores if not row[2]),default=(0.,'',False))
            # A rejected year that scores as well as the approved year cannot
            # be accepted as PASS. The old +.008 margin let a 2025 label pass.
            mismatch=bad[0]>=.75 and bad[0]>=good[0] if field=='year' else bad[0]>=.75 and bad[0]>good[0]+.008
            insufficient=good[0] < (.72 if field=='qc' else .80)
            if (field=='year' and not mismatch and bad[0]>=.90
                    and good[0]-bad[0]<.02):
                # Near-tied 2025/2026 scores cannot authorize PASS.
                insufficient=True
            fields[field]={'approved_score':good[0],'rejected_score':bad[0],
                           'closest_rejected':bad[1],'mismatch':mismatch,'insufficient':insufficient}
            if mismatch:reasons.append('wrong '+('QC text' if field=='qc' else 'year'))
            elif insufficient:reasons.append('unconfirmed '+field+' field')
        if added:reasons.append('added marks on label')
        if torn:reasons.append('torn label / exposed cardboard')
        return {'passed':not reasons,'reasons':reasons,'added_mark_components':added,
                'torn_paper_components':torn,'critical_fields':fields,
                'field_reference_sha256':self.assets,'calibrated':False}
