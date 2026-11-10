@echo off
rem =============================================================================
rem Quy trình chuyển đổi & Lượng tử hóa mô hình YOLOv8n sang NCNN FP16
rem Tham chiếu Thuyết minh ĐATN: Mục 3.2.3.3
rem =============================================================================

if "%~1"=="" (
  echo Cach dung: export_ncnn.bat F:\DATN\Cong_cu_phat_trien\work\fp16_thu_nghiem_moi
  exit /b 2
)
echo Xuat ung vien NCNN FP16, khong thay model tren Pi...
python "%~dp0export_ncnn.py" --output-root "%~1"
if errorlevel 1 exit /b 1
echo Da xuat ung vien. Can kiem tra hoi quy va do toc do tren Pi truoc khi trien khai.

