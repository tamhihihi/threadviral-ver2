@echo off
title KET NOI TU XA 4G/5G CHO DIEN THOAI QUA CLOUDFLARE TUNNEL
echo ======================================================================
echo    KET NOI TU XA CHO IPHONE & ANDROID (KHONG CAN CHUNG WI-FI)
echo ======================================================================
echo.
where cloudflared >nul 2>&1
if %errorlevel% neq 0 (
    if not exist "%~dp0cloudflared.exe" (
        echo Dang tai cloudflared (khoang 15MB, chi tai 1 lan duy nhat)...
        powershell -Command "Invoke-WebRequest -Uri 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe' -OutFile '%~dp0cloudflared.exe'"
    )
    set CF_EXE="%~dp0cloudflared.exe"
) else (
    set CF_EXE=cloudflared
)

echo.
echo ======================================================================
echo    DANG KHOI TAO DUONG LINK HTTPS (MIEN PHI & BAO MAT)...
echo    Copy duong link *.trycloudflare.com xuat hien ben duoi de mo tren dien thoai:
echo ======================================================================
echo.
%CF_EXE% tunnel --url http://127.0.0.1:8000
pause

