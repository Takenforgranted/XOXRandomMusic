@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo    听歌猜名挑战 · 网页版启动中...
echo    启动后将自动打开浏览器访问本机网页
echo    关闭此窗口即停止游戏服务器
echo ============================================
echo.
python web_server.py
echo.
echo 服务器已退出。按任意键关闭窗口...
pause >nul
