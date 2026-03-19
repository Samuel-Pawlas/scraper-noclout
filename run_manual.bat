@echo off
REM Noclout Scraper - Manual Run
REM Double-click this file or run from command line to execute

echo ============================================================
echo Noclout Scraper - Manual Run
echo ============================================================
echo.

REM Set script directory
set SCRIPT_DIR=%~dp0

REM Python path (update if different)
set PYTHON_PATH=%USERPROFILE%\AppData\Local\Programs\Python\Python312\python.exe

REM Check Python exists
if not exist "%PYTHON_PATH%" (
    echo ERROR: Python not found at %PYTHON_PATH%
    echo Please install Python 3.12 from https://python.org
    pause
    exit /b 1
)

REM Install dependencies if needed
echo Checking dependencies...
"%PYTHON_PATH%" -m pip install -q -r "%SCRIPT_DIR%requirements.txt"
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)

REM Run the scraper
echo Starting scraper...
echo.
"%PYTHON_PATH%" "%SCRIPT_DIR%scraper.py"

if errorlevel 1 (
    echo.
    echo ============================================================
    echo Scraper failed with error code %errorlevel%
    echo ============================================================
    pause
    exit /b 1
) else (
    echo.
    echo ============================================================
    echo Scraper completed successfully!
    echo ============================================================
)

pause
