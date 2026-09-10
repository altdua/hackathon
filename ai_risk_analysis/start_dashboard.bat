@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel% equ 0 (
    py -3 -c "import tkinter" >nul 2>nul
    if not errorlevel 1 (
        py -3 main.py
        goto done
    )
)
python -c "import tkinter" >nul 2>nul
if %errorlevel% equ 0 (
    python main.py
    goto done
)
if exist "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" (
    "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" main.py
    goto done
)
echo Python with Tk support was not found. Install Python and enable Tcl/Tk.
pause
exit /b 1
:done
if errorlevel 1 pause
