@echo off
chcp 65001 >nul
cd /d "%~dp0"
title PixelPainter
echo ============================================
echo   PixelPainter - 픽셀아트 변환 패널
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo [오류] Python이 설치되어 있지 않습니다.
  echo        https://www.python.org/downloads/ 에서 설치하세요.
  echo        설치 화면에서 "Add Python to PATH" 를 꼭 체크하세요.
  echo.
  pause
  exit /b 1
)

python -c "import gradio, PIL, numpy, scipy, sklearn" >nul 2>nul
if errorlevel 1 (
  echo [최초 실행] 필요한 패키지를 설치합니다. 몇 분 걸릴 수 있어요...
  python -m pip install --upgrade pip
  python -m pip install gradio pillow numpy scipy scikit-learn
  echo.
)

echo 브라우저가 자동으로 열립니다.
echo (안 열리면 http://127.0.0.1:7860 로 접속하세요)
echo 종료하려면 이 창에서 Ctrl+C 를 누르거나 창을 닫으세요.
echo.
python gui.py
pause
