@echo off
chcp 65001 >nul
setlocal

python --version >nul 2>&1 || (echo 请先安装 Python 并加入 PATH & pause & exit /b 1)

if not exist ".venv" python -m venv .venv
call .venv\Scripts\activate.bat

python -m pip install --upgrade pip
pip install requests pandas openpyxl

echo 安装完成。
pause
endlocal