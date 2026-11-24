@echo off
rem Aarya Chiripal, AME 310 Engineering Thermodynamics I, Prof. Penkova, USC, Fall 2026.
rem H2 Fast-Fill Lab, run.bat: double-click launcher for Windows. It starts the app; it is not part of the model.
rem First run creates a virtual environment and installs the pinned packages.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Setting up the app for the first time. This takes a minute or two.
    py -3 -m venv .venv 2>nul || python -m venv .venv
    if not exist ".venv\Scripts\python.exe" (
        echo Python 3.10 or newer is needed. Install it from https://www.python.org/downloads/windows/ and run this file again.
        pause
        exit /b 1
    )
    ".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Package install failed. Check the internet connection and run again.
        pause
        exit /b 1
    )
)
echo Starting H2 Fast-Fill Lab. Close this window to stop the app.
".venv\Scripts\python.exe" -m streamlit run app.py --server.headless true --browser.gatherUsageStats false
pause
