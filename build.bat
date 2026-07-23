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
if exist dist\Vitra rmdir /s /q dist\Vitra

echo [4/5] Building Vitra onedir distribution...
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm Vitra.spec || exit /b 1

echo [5/5] Copying extension, icons, notices, and optional offline models...
xcopy browser_extension dist\Vitra\browser_extension\ /E /I /Y >nul
copy /Y assets\icon-v2.ico dist\Vitra\Vitra.ico >nul
copy /Y packaging\desktop.ini dist\Vitra\desktop.ini >nul
attrib +h dist\Vitra\Vitra.ico
attrib +h +s dist\Vitra\desktop.ini
attrib +r dist\Vitra
copy /Y README.md dist\Vitra\ >nul
copy /Y README.vi.md dist\Vitra\ >nul
copy /Y THIRD_PARTY_NOTICES.md dist\Vitra\ >nul
copy /Y LICENSE dist\Vitra\ >nul
.\.venv\Scripts\python.exe scripts\copy_licenses.py dist\Vitra\THIRD_PARTY_LICENSES || exit /b 1
if /I "%~1"=="--offline" xcopy models dist\Vitra\models\ /E /I /Y >nul

echo.
echo Build completed: dist\Vitra\Vitra.exe
if /I "%~1"=="--offline" echo Offline models were included.
endlocal
