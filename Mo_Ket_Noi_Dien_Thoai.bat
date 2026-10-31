@echo off
title MO KET NOI CHO DIEN THOAI (PORT 8000)
echo ======================================================================
echo    DANG CAU HINH WINDOWS FIREWALL CHO PHEP KET NOI TU DIEN THOAI...
echo ======================================================================
echo.
netsh advfirewall firewall delete rule name="ThreadViral Port 8000" >nul 2>&1
netsh advfirewall firewall add rule name="ThreadViral Port 8000" dir=in action=allow protocol=TCP localport=8000
echo.
echo ======================================================================
echo    DA MO PORT 8000 CHO DIEN THOAI (IPHONE/ANDROID) THANH CONG!
echo ======================================================================
pause

