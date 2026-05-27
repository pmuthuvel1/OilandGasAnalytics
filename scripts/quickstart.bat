# Oil & Gas Analytics - Quick Start Guide for Windows

@echo off
cls
echo.
echo ==========================================
echo Oil ^& Gas Analytics Multi-Agent System
echo ==========================================
echo.

REM Check Python version
python --version
if errorlevel 1 (
    echo Error: Python not found. Please install Python 3.11+
    pause
    exit /b 1
)
echo ✓ Python found
echo.

REM Create virtual environment if needed
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    echo ✓ Virtual environment created
)

REM Activate virtual environment
call venv\Scripts\activate.bat
echo ✓ Virtual environment activated
echo.

REM Install dependencies
echo Installing dependencies...
pip install -q -r requirements.txt
echo ✓ Dependencies installed
echo.

REM Create directories
mkdir logs 2>nul
mkdir data\uploads 2>nul

REM Check .env file
if not exist ".env" (
    echo ⚠ .env file not found!
    echo Creating .env from .env.example...
    copy .env.example .env
    echo ✓ .env created - Please edit and add your OPENAI_API_KEY
    echo.
    pause
    exit /b 1
)

echo.
echo ==========================================
echo Ready to start!
echo ==========================================
echo.
echo Start services in separate terminals:
echo.
echo Command Prompt 1 (API - port 8000):
echo   python run.py
echo.
echo Command Prompt 2 (UI - port 8001):
echo   python run_ui.py
echo.
echo Or run everything with Docker:
echo   docker build -t oil-gas-analytics .
echo   docker run -p 8000:8000 -p 8001:8001 --env-file .env oil-gas-analytics
echo.
echo Access the system:
echo   - API: http://localhost:8000
echo   - Dashboard: http://localhost:8001
echo   - Docs: http://localhost:8000/docs
echo.
pause
