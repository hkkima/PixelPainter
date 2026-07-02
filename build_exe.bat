@echo off
chcp 65001 >nul
cd /d "%~dp0"
title PixelPainter - EXE 빌드
echo ============================================
echo   PixelPainter.exe 빌드
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo [오류] Python이 필요합니다. https://www.python.org/downloads/
  pause
  exit /b 1
)

echo [1/2] 빌드 도구 및 의존성 설치...
python -m pip install --upgrade pyinstaller gradio pillow numpy scipy scikit-learn

echo.
echo [2/2] PyInstaller 로 빌드 중... (몇 분 소요)
pyinstaller --noconfirm --clean --onedir --name PixelPainter ^
  --collect-all gradio ^
  --collect-all gradio_client ^
  --collect-all safehttpx ^
  --collect-all groovy ^
  --collect-data sklearn ^
  --add-data "pxcore.py;." ^
  gui.py

echo.
echo ============================================
echo  완료!  dist\PixelPainter\PixelPainter.exe
echo.
echo  * 샘플 이미지를 보이게 하려면 kkami*.png 들을
echo    dist\PixelPainter\ 폴더로 복사하세요.
echo  * 폴더째 배포하면 됩니다(단일 exe가 아닌 폴더형).
echo ============================================
pause
