@echo off
chcp 65001 >nul
echo ============================================================
echo   法人買賣超選股系統 - 麥克連選股法
echo   啟動後請開啟瀏覽器訪問: http://localhost:5000
echo ============================================================
echo.

set PYTHON=C:\Users\Ivan.shih\AppData\Local\Programs\Python\Python312\python.exe

cd /d "%~dp0"
"%PYTHON%" app.py

pause
