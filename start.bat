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

:: 1. RTMP Sunucu - minimize pencerede baslat
echo [1/3] RTMP Sunucu baslatiliyor...
start /min "RTMP Server" cmd /c "cd /d "%~dp0" && node rtmp-server.js"
timeout /t 3 /nobreak >nul

:: 2. Cloudflare Tunnel - minimize pencerede baslat, URL'yi yakala
echo [2/3] Cloudflare Tunnel baslatiliyor...
if not exist "%~dp0logs" mkdir "%~dp0logs"
start /min "Cloudflare Tunnel" cmd /c "cloudflared tunnel --url tcp://localhost:1935 > "%~dp0logs\cloudflare.log" 2>&1"

:: URL gelene kadar bekle (max 20 saniye)
echo       Cloudflare URL bekleniyor...
set CF_URL=
for /l %%i in (1,1,20) do (
    timeout /t 1 /nobreak >nul
    for /f "tokens=*" %%a in ('findstr /i "trycloudflare.com" "%~dp0logs\cloudflare.log" 2^>nul') do (
        set CF_LINE=%%a
    )
    if defined CF_LINE goto :found
)

:found
echo.
echo ============================================
for /f "tokens=*" %%a in ('findstr /i "trycloudflare.com" "%~dp0logs\cloudflare.log" 2^>nul') do (
    echo   Cloudflare: %%a
)
echo.
echo   RTMP Adresiniz (Media Source icin kopyalayin):
for /f "tokens=2 delims=|" %%a in ('findstr /i "trycloudflare.com" "%~dp0logs\cloudflare.log" 2^>nul') do (
    set HOST=%%a
)
for /f "tokens=*" %%h in ('findstr /i "trycloudflare.com" "%~dp0logs\cloudflare.log" 2^>nul ^| findstr /i "https://"') do (
    for /f "tokens=2 delims=/" %%d in ("%%h") do (
        echo   rtmp://%%d:1935/live/camera
    )
)
echo ============================================
echo.

:: 3. Watchdog - bu pencerede on planda calistir
echo [3/3] Watchdog baslatiliyor... (CTRL+C ile durdurulur)
echo.
python "%~dp0watchdog.py"

echo.
echo Watchdog durduruldu. Diger servisler hala calisiyor olabilir.
pause
