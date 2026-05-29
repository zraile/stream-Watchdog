@echo off
cd /d "%~dp0"
title Stream Watchdog

echo ============================================
echo   Stream Watchdog - Baslatiliyor
echo ============================================
echo.

:: Gerekli araclari kontrol et
where cloudflared >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [HATA] cloudflared bulunamadi: https://github.com/cloudflare/cloudflared/releases
    pause & exit /b 1
)
where node >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [HATA] Node.js bulunamadi: https://nodejs.org
    pause & exit /b 1
)
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [HATA] Python bulunamadi: https://python.org
    pause & exit /b 1
)

:: logs klasoru olustur
if not exist "%~dp0logs" mkdir "%~dp0logs"

:: 1. RTMP Sunucu - arka planda, log dosyasina yaz
echo [1/3] RTMP Sunucu baslatiliyor...
start /b "" node "%~dp0rtmp-server.js" > "%~dp0logs\rtmp.log" 2>&1
timeout /t 3 /nobreak >nul

:: 2. Cloudflare Tunnel - arka planda, log dosyasina yaz
echo [2/3] Cloudflare Tunnel baslatiliyor...
start /b "" cloudflared tunnel --url tcp://localhost:1935 > "%~dp0logs\cloudflare.log" 2>&1
echo       Cloudflare adresi: logs\cloudflare.log dosyasinda goruntulenir
timeout /t 5 /nobreak >nul

:: Cloudflare adresini logdan bul ve goster
echo.
echo --- Cloudflare Tunnel Adresi ---
findstr /i "trycloudflare.com" "%~dp0logs\cloudflare.log" 2>nul
echo --------------------------------
echo RTMP adresiniz: rtmp://[YUKARDAKI_ADRES]:1935/live/camera
echo.

:: 3. Watchdog - on planda calistir (tum log bu pencerede gorunur)
echo [3/3] Watchdog baslatiliyor...
echo ============================================
echo   Kapatmak icin CTRL+C
echo ============================================
echo.
python "%~dp0watchdog.py"

echo.
echo Tum servisler durduruldu.
pause
