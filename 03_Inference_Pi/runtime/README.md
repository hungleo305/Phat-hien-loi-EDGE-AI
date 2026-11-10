# Closed inventory trial — 30/10/2026

This package is an isolated candidate for the recorded physical boxes. It
retains the fast2 whole/surface NCNN models and approved label assets. The
fixed-camera guard adds missing-label detection, a narrow warped-silhouette
check, and a re-adjudicated PASS13 border false alarm. It is valid only for
1280x720 captures with the recorded box placement and lighting.

The original fast2 `samples/review.jpg` is byte-identical to the user's
PASS13 image. This trial expects PASS for that sample; the original fast2
self-check expects REVIEW. This is an intentional change in ground truth,
not a claim that the legacy self-check is unchanged.

Run `python self_check.py --backend ncnn` after copying to Pi. Replay all
recorded images and then run the *same owned boxes* again through the real
camera and station before acceptance. Do not replace the production runtime.
The 466/466 laptop result is a tuned regression, not a direct Pi timing or
live CAPTURE-to-RESULT measurement. See sibling REPORT.md.
