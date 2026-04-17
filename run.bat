@echo off
chcp 65001 >nul
call .venv\Scripts\activate.bat
python worldtides_gui_downloader.py
pause