@echo off
cd /d d:\code_space\cross_chat\backend
call ..\venv\Scripts\activate.bat
python mvp_backend.py --room-id 13619077
pause
