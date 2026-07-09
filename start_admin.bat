@echo off
chcp 65001 >nul
echo Starting TG Links Manager...
echo.
echo Dashboard: http://127.0.0.1:8765/admin.html
echo Press Ctrl+C to stop.
echo.
C:\Users\admin\.workbuddy\binaries\python\versions\3.13.12\python.exe D:\workspace\Claw\tggroup-repo\admin_server.py
pause
