@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 转换课表

echo ============================================
echo   把 课程表.xlsx 转成 schedule.json
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [错误] 没有找到 Python。
    echo.
    echo 这台电脑需要先装 Python 才能换课表。
    echo 如果只是想看时钟，双击「桌面时钟.exe」就行，不需要 Python。
    echo.
    pause
    exit /b 1
)

echo 正在转换，请稍等...
echo.

python convert.py %*
set RC=%ERRORLEVEL%

echo.
if "%RC%"=="0" (
    echo [完成] schedule.json 已更新，时钟会在 10 秒内自动刷新。
) else (
    echo [失败] 转换没有成功，请看上面的错误提示。
)

echo.
pause
exit /b %RC%
