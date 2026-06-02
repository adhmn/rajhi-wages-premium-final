@echo off
pip install -r requirements.txt
pyinstaller --onefile --windowed --name "Rajhi-Wages-Premium" --collect-all customtkinter --collect-all openpyxl --collect-all xlrd run.py
pause
