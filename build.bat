@echo off
setlocal
cd /d "%~dp0"

REM The python.exe App Execution Alias is not a real interpreter. Prefer the py launcher.
where py >nul 2>&1
if %errorlevel%==0 (
    set "PYLAUNCH=py -3"
) else (
    set "PYLAUNCH=python"
)

if not exist "venv\Scripts\python.exe" (
    %PYLAUNCH% -m venv venv
    if errorlevel 1 (
        echo Failed to create venv. Install Python 3.10 or newer and try again.
        exit /b 1
    )
)

venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 exit /b 1

venv\Scripts\python.exe -m pip install pyinstaller tkinterdnd2 "packages/markitdown[all]"
if errorlevel 1 exit /b 1

venv\Scripts\python.exe -m PyInstaller --noconfirm --clean build.spec
if errorlevel 1 exit /b 1

echo.
echo Built dist\MarkItDown\MarkItDown.exe
echo Keep the whole dist\MarkItDown folder together when you copy the app.
endlocal
