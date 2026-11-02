@echo off
rem =============================================================================
rem Quy trình chuyển đổi & Lượng tử hóa mô hình YOLOv8n sang NCNN FP16
rem Tham chiếu Thuyết minh ĐATN: Mục 3.2.3.3
rem =============================================================================

echo [Buoc 1] Xuat truc tiep YOLOv8 sang NCNN FP16 bang Ultralytics...
python export_ncnn.py
echo [Hoan tat] Cac mo hinh NCNN FP16 duoc luu trong thu muc ncnn_models/
pause

