@echo off
cd /d "%~dp0"
echo ============================================
echo   Alchequant - Starting...
echo   http://localhost:8501
echo ============================================

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python was not found. Please install Python 3.10+ or activate your virtual environment.
    pause
    exit /b 1
)

python -c "import streamlit" >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Streamlit is not installed in the current Python environment.
    echo Run: python -m pip install -r requirements.txt
    pause
    exit /b 1
)

start "" http://localhost:8501
python -m streamlit run app.py --server.port 8501
pause
