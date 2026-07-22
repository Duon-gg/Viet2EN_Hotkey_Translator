@echo off
setlocal
cd /d "%~dp0"

echo [1/5] Checking dependencies...
.\.venv\Scripts\python.exe -m pip check || exit /b 1

echo [2/5] Running quality checks...
.\.venv\Scripts\python.exe -m ruff check main.py core ui utils scripts tests || exit /b 1
.\.venv\Scripts\python.exe -m mypy main.py core ui utils scripts || exit /b 1
.\.venv\Scripts\python.exe -m pytest -q || exit /b 1

echo [3/5] Cleaning previous PyInstaller output...
if exist build rmdir /s /q build
if exist dist\Viet2EN rmdir /s /q dist\Viet2EN

echo [4/5] Building Viet2EN onedir distribution...
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm Viet2EN.spec || exit /b 1

echo [5/5] Copying extension, icons, notices, and optional offline models...
xcopy browser_extension dist\Viet2EN\browser_extension\ /E /I /Y >nul
copy /Y assets\icon-v2.ico dist\Viet2EN\Viet2EN.ico >nul
copy /Y packaging\desktop.ini dist\Viet2EN\desktop.ini >nul
attrib +h dist\Viet2EN\Viet2EN.ico
attrib +h +s dist\Viet2EN\desktop.ini
attrib +r dist\Viet2EN
copy /Y README.md dist\Viet2EN\ >nul
copy /Y README.vi.md dist\Viet2EN\ >nul
copy /Y THIRD_PARTY_NOTICES.md dist\Viet2EN\ >nul
copy /Y LICENSE dist\Viet2EN\ >nul
.\.venv\Scripts\python.exe scripts\copy_licenses.py dist\Viet2EN\THIRD_PARTY_LICENSES || exit /b 1
if /I "%~1"=="--offline" xcopy models dist\Viet2EN\models\ /E /I /Y >nul

echo.
echo Build completed: dist\Viet2EN\Viet2EN.exe
if /I "%~1"=="--offline" echo Offline models were included.
endlocal
