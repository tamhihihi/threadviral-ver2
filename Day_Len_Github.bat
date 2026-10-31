@echo off
title DAY CODE THREADVIRAL LEN GITHUB
echo ======================================================================
echo    HUONG DAN DAY CODE LEN GITHUB:
echo    1. Vao https://github.com/new tao 1 repo moi (VD: threadviral)
echo    2. Copy duong link HTTPS (VD: https://github.com/Treestore/threadviral.git)
echo ======================================================================
echo.
set /p REPO_URL="Dan link GitHub repository cua ban vao day: "
if "%REPO_URL%"=="" (
    echo Ban chua nhap link!
    pause
    exit /b
)
git remote remove origin >nul 2>&1
git remote add origin %REPO_URL%
echo.
echo Dang day code len GitHub (nhanh hay cham tuy vao toc do mang)...
git push -u origin main
echo.
echo ======================================================================
echo    DA HOAN TAT! HAY KIEM TRA TREN TRANG GITHUB CUA BAN.
echo ======================================================================
pause
