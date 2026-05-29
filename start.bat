@echo off
echo ============================================
echo   Stream Watchdog - Baslatiliyor
echo ============================================
echo.

:: cloudflared kurulu mu kontrol et
where cloudflared >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [HATA] cloudflared bulunamadi. Lutfen yükleyin:
    echo   https://github.com/cloudflare/cloudflared/releases
    pause
    exit /b 1
)

:: 1. RTMP Sunucuyu başlat
echo [1/3] RTMP Sunucu baslatiliyor...
start "RTMP Server" cmd /k "node rtmp-server.js"
timeout /t 3 /nobreak >nul

:: 2. Cloudflare Tunnel başlat (localhost:1935 → dışarıya açar)
echo [2/3] Cloudflare Tunnel baslatiliyor...
start "Cloudflare Tunnel" cmd /k "cloudflared tunnel --url tcp://localhost:1935"
timeout /t 3 /nobreak >nul

:: 3. Watchdog'u başlat
echo [3/3] Watchdog baslatiliyor...
start "Watchdog" cmd /k "python watchdog.py"

echo.
echo Tum servisler baslatildi!
echo.
echo NOT: Cloudflare Tunnel penceresinden kameranin RTMP adresini kopyalayin.
echo Ornek: rtmp://abc123.trycloudflare.com:1935/live/camera
echo.
pause
