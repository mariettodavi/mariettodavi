@echo off
cd /d %~dp0
python -m pip install --disable-pip-version-check -q -r requirements.txt
python app.py
pause
