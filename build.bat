@echo off
title Build Viet2EN Translator
cd /d "%~dp0"

echo [1/3] Dang xoa thu muc build cu...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [2/3] Dang cai dat PyInstaller...
.\.venv\Scripts\python.exe -m pip install pyinstaller

echo [3/3] Dang dong goi thanh 1 file duy nhat (Onefile Mode)...
.\.venv\Scripts\python.exe -m PyInstaller ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name "Viet2EN" ^
    --icon="assets/icon.ico" ^
    --hidden-import "argostranslate" ^
    --hidden-import "pystray._win32" ^
    --hidden-import "keyboard" ^
    --hidden-import "pyperclip" ^
    main.py

echo.
echo ==========================================================
echo [THANG CONG] File .exe da duoc luu tai: dist\Viet2EN.exe
echo ==========================================================

