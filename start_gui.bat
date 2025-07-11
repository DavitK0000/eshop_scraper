@echo off
echo Starting E-commerce Scraper GUI Tester...
echo.

REM Check if virtual environment exists
if not exist ".venv\Scripts\activate.bat" (
    echo Virtual environment not found. Creating one...
    python -m venv .venv
)

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Install dependencies if requirements.txt exists
if exist "requirements.txt" (
    echo Installing dependencies...
    pip install -r requirements.txt
)

REM Start the GUI
echo Starting GUI tester...
echo Make sure the API server is running at http://localhost:8000
echo.
python gui_test.py

pause 