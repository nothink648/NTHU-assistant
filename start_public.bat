@echo off
chcp 65001 >nul
setlocal EnableExtensions
title 校園助手 - 外網模式
cd /d "%~dp0"

rem ====== 設定 ======
set "PORT=8501"
rem ==================

rem --- 找 cloudflared（剛安裝完 PATH 可能還沒更新，所以也找預設安裝位置）---
set "CF=cloudflared"
where cloudflared >nul 2>&1 || (
  if exist "%ProgramFiles(x86)%\cloudflared\cloudflared.exe" set "CF=%ProgramFiles(x86)%\cloudflared\cloudflared.exe"
  if exist "%ProgramFiles%\cloudflared\cloudflared.exe" set "CF=%ProgramFiles%\cloudflared\cloudflared.exe"
)
"%CF%" --version >nul 2>&1 || (
  echo [錯誤] 找不到 cloudflared，請先執行：winget install Cloudflare.cloudflared
  pause & exit /b 1
)

if not exist logs mkdir logs
if exist public_url.txt del public_url.txt

rem --- 1. 啟動 App（只聽本機 127.0.0.1，外面的人只能透過 Cloudflare 網址連進來）---
curl -s -o nul -m 2 http://127.0.0.1:%PORT%/_stcore/health && (
  echo App 已經在 port %PORT% 執行中，直接使用。
) || (
  echo [1/2] 啟動校園助手 App ...
  start "" /b python -m streamlit run app.py --server.port %PORT% --server.address 127.0.0.1 --server.headless true --browser.gatherUsageStats false >logs\streamlit.log 2>&1
)

set /a N=0
:wait_app
curl -s -o nul -m 2 http://127.0.0.1:%PORT%/_stcore/health && goto app_ok
set /a N+=1
if %N% geq 30 (
  echo [錯誤] App 60 秒內沒有啟動，請看 logs\streamlit.log
  pause & exit /b 1
)
ping -n 3 127.0.0.1 >nul
goto wait_app
:app_ok
echo       App 已啟動：http://localhost:%PORT%

rem --- 2. 建立 Cloudflare 臨時通道，取得外網網址 ---
echo [2/2] 建立外網網址（約 5–15 秒）...
start "" /b "%CF%" tunnel --no-autoupdate --url http://127.0.0.1:%PORT% >logs\cloudflared.log 2>&1

set "URL="
set /a N=0
:wait_url
ping -n 3 127.0.0.1 >nul
for /f "usebackq delims=" %%u in (`powershell -NoProfile -Command "$m = Select-String -Path 'logs\cloudflared.log' -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' -ErrorAction SilentlyContinue | Select-Object -First 1; if ($m) { $m.Matches[0].Value }"`) do set "URL=%%u"
if defined URL goto url_ok
set /a N+=1
if %N% geq 30 (
  echo [錯誤] 60 秒內沒有拿到外網網址，請看 logs\cloudflared.log
  pause & exit /b 1
)
goto wait_url
:url_ok

echo %URL%> public_url.txt
echo %URL%| clip
echo.
echo  ==============================================================
echo    外網網址（已複製到剪貼簿，也存在 public_url.txt）：
echo.
echo      %URL%
echo.
echo    * 把這個網址傳給同學就能使用；第一次開可能要等幾秒
echo    * 每次重新啟動網址都會不同
echo    * 電腦不能睡眠或關機，關掉這個視窗 = 停止服務
echo  ==============================================================
echo.
if not defined NO_BROWSER start "" "%URL%"

echo 服務執行中。按任意鍵停止 App 與外網網址...
pause >nul
taskkill /f /im cloudflared.exe >nul 2>&1
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /r /c:"127.0.0.1:%PORT% .*LISTENING"') do taskkill /f /pid %%p >nul 2>&1
echo 已停止。
ping -n 3 127.0.0.1 >nul
