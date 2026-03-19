@echo off
REM Noclout Scraper - Manual Run
REM Double-click this file or run from command line

echo ============================================================
echo Noclout Scraper - Manual Run
echo ============================================================
echo.

set SCRIPT_DIR=%~dp0
set SCRIPT_DIR=%SCRIPT_DIR:~0,-1%

REM Try multiple Python paths
where python >nul 2>&1
if %errorlevel%==0 (
    set PYTHON=python
) else (
    where py >nul 2>&1
    if %errorlevel%==0 (
        set PYTHON=py
    ) else (
        if exist "%USERPROFILE%\AppData\Local\Programs\Python\Python312\python.exe" (
            set PYTHON=%USERPROFILE%\AppData\Local\Programs\Python\Python312\python.exe
        ) else (
            echo ERROR: Python not found
            echo Please install Python 3.12 from https://python.org
            pause
            exit /b 1
        )
    )
)

echo Using Python: %PYTHON%
echo.

REM Check Python version
%PYTHON% --version
if errorlevel 1 (
    echo ERROR: Failed to run Python
    pause
    exit /b 1
)
echo.

REM Check dependencies
echo Checking dependencies...
%PYTHON% -c "import requests, bs4, supabase, PIL, numpy, torch, transformers" 2>nul
if errorlevel 1 (
    echo Installing dependencies...
    %PYTHON% -m pip install -r "%SCRIPT_DIR%\requirements.txt" -q
    if errorlevel 1 (
        echo ERROR: Failed to install dependencies
        pause
        exit /b 1
    )
    echo Dependencies installed
)
echo.

REM Run the scraper
echo Starting scraper...
echo.
cd /d "%SCRIPT_DIR%"
%PYTHON% "%SCRIPT_DIR%\scraper.py"

if errorlevel 1 (
    echo.
    echo ============================================================
    echo Scraper failed!
    echo Check scraper_errors.log for details
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
