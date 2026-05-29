@echo off
cd /d "%~dp0"
title Stream Watchdog
echo ============================================
echo   Stream Watchdog - Baslatiliyor
echo ============================================
echo.

:: cloudflared kurulu mu kontrol et
where cloudflared >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [HATA] cloudflared bulunamadi. Lutfen yukleyin:
    echo   https://github.com/cloudflare/cloudflared/releases
    pause
    exit /b 1
)

:: node kurulu mu kontrol et
where node >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [HATA] Node.js bulunamadi. Lutfen yukleyin:
    echo   https://nodejs.org
    pause
    exit /b 1
)

:: python kurulu mu kontrol et
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [HATA] Python bulunamadi. Lutfen yukleyin:
    echo   https://python.org
    pause
    exit /b 1
)

echo [1/3] RTMP Sunucu baslatiliyor...
start /b "" node "%~dp0rtmp-server.js" >> "%~dp0logs\rtmp.log" 2>&1

timeout /t 3 /nobreak >nul

echo [2/3] Cloudflare Tunnel baslatiliyor...
start /b "" cloudflared tunnel --url tcp://localhost:1935 2>&1 | "%SystemRoot%\System32\findstr" /v "^$" | powershell -NoProfile -Command ^
  "$input | ForEach-Object { $line = $_; if ($line -match 'trycloudflare\.com') { Write-Host \"[CLOUDFLARE] $line\" -ForegroundColor Cyan } else { Write-Host \"[CLOUDFLARE] $line\" } }" &

timeout /t 3 /nobreak >nul

echo [3/3] Watchdog baslatiliyor...
echo.
echo ============================================
echo   Tum servisler tek pencerede izleniyor
echo   Kapatmak icin CTRL+C
echo ============================================
echo.

:: Cloudflare logunu goster ve watchdog'u on planda calistir
powershell -NoProfile -Command ^
  "Set-Location '%~dp0'; " ^
  "$cf = Start-Process -FilePath 'cloudflared' -ArgumentList 'tunnel','--url','tcp://localhost:1935' -NoNewWindow -PassThru -RedirectStandardError '%~dp0logs\cloudflare.log'; " ^
  "Start-Sleep 3; " ^
  "Write-Host ''; " ^
  "Write-Host '[INFO] Cloudflare tunnel baslatildi. Log: logs\cloudflare.log' -ForegroundColor Yellow; " ^
  "Write-Host '[INFO] RTMP Sunucu: http://localhost:8000 (HTTP Panel)' -ForegroundColor Green; " ^
  "Write-Host ''; " ^
  "python '%~dp0watchdog.py'"

echo.
echo Tum servisler durduruldu.
pause
