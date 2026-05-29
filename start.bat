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

:: logs klasoru olustur, eski logu sil
if not exist "%~dp0logs" mkdir "%~dp0logs"
del /f /q "%~dp0logs\cloudflare.log" >nul 2>&1

:: 1. RTMP Sunucu - minimize pencerede baslat
echo [1/3] RTMP Sunucu baslatiliyor...
start /min "RTMP Server" cmd /c "cd /d "%~dp0" && node rtmp-server.js"
timeout /t 3 /nobreak >nul

:: 2. Cloudflare Tunnel - minimize pencerede baslat
echo [2/3] Cloudflare Tunnel baslatiliyor...
start /min "Cloudflare Tunnel" cmd /c "cloudflared tunnel --url tcp://localhost:1935 >> "%~dp0logs\cloudflare.log" 2>&1"

:: URL gelene kadar bekle - sadece https://xxx.trycloudflare.com satirini bul
echo       Cloudflare URL bekleniyor...
set CF_HOST=

:wait_loop
timeout /t 2 /nobreak >nul
:: Sadece https:// ile baslayan ve trycloudflare.com iceren satiri al
for /f "tokens=*" %%a in ('findstr /r "^  https://.*trycloudflare\.com" "%~dp0logs\cloudflare.log" 2^>nul') do (
    set CF_RAW=%%a
)
if not defined CF_RAW goto :wait_loop

:: Boslukları temizle, sadece URL'yi al
for /f "tokens=* delims= " %%a in ("%CF_RAW%") do set CF_URL=%%a

:: https:// kaldir, sadece hostname al
set CF_HOST=%CF_URL:https://=%
set CF_HOST=%CF_HOST: =%

echo.
echo ============================================
echo   Cloudflare hazir!
echo.
echo   HTTPS Adresi  : https://%CF_HOST%
echo   RTMP Adresi   : rtmp://%CF_HOST%:1935/live/camera
echo.
echo   >>> Streamlabs Media Source icin kopyala:
echo   rtmp://%CF_HOST%:1935/live/camera
echo ============================================
echo.

:: 3. Watchdog - bu pencerede on planda calistir
echo [3/3] Watchdog baslatiliyor... (CTRL+C ile durdurulur)
echo.
python "%~dp0watchdog.py"

echo.
echo Watchdog durduruldu.
pause
