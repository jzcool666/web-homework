@echo off
setlocal DisableDelayedExpansion
chcp 65001 >nul
for %%I in ("%~dp0..") do set "PROJECT_ROOT=%%~fI"
set "PYTHONUTF8=1"
if exist "%PROJECT_ROOT%\portable.json" (
    if not exist "%PROJECT_ROOT%\runtime\python\python.exe" goto missing_portable
    "%PROJECT_ROOT%\runtime\python\python.exe" -u "%PROJECT_ROOT%\scripts\start_local.py" %*
    goto finished
)

if exist "%PROJECT_ROOT%\.local-run\venv\Scripts\python.exe" (
    "%PROJECT_ROOT%\.local-run\venv\Scripts\python.exe" -c "import sys; assert (3,12) <= sys.version_info[:2] <= (3,14) and sys.maxsize > 2**32" >nul 2>nul
    if not errorlevel 1 goto local_python
)
if exist "%PROJECT_ROOT%\venv\Scripts\python.exe" (
    "%PROJECT_ROOT%\venv\Scripts\python.exe" -c "import sys; assert (3,12) <= sys.version_info[:2] <= (3,14) and sys.maxsize > 2**32" >nul 2>nul
    if not errorlevel 1 goto project_python
)
where py >nul 2>nul
if errorlevel 1 goto try_python
for %%V in (3.14 3.13 3.12) do (
    py -%%V -c "import sys; assert sys.maxsize > 2**32" >nul 2>nul
    if not errorlevel 1 (
        set "PY_VERSION=%%V"
        goto py_launcher
    )
)
:try_python
where python >nul 2>nul
if errorlevel 1 goto missing_python
python -c "import sys; assert (3,12) <= sys.version_info[:2] <= (3,14) and sys.maxsize > 2**32" >nul 2>nul
if errorlevel 1 goto missing_python
python -u "%PROJECT_ROOT%\scripts\start_local.py" %*
goto finished
:local_python
"%PROJECT_ROOT%\.local-run\venv\Scripts\python.exe" -u "%PROJECT_ROOT%\scripts\start_local.py" %*
goto finished
:project_python
"%PROJECT_ROOT%\venv\Scripts\python.exe" -u "%PROJECT_ROOT%\scripts\start_local.py" %*
goto finished
:py_launcher
py -%PY_VERSION% -u "%PROJECT_ROOT%\scripts\start_local.py" %*
goto finished
:missing_python
echo Python 3.12-3.14 64-bit is required. Recommended: Python 3.14.
echo Install from https://www.python.org/downloads/windows/
echo Select "Add python.exe to PATH", then double-click the launcher again.
set "RESULT=1"
goto wait_exit
:finished
set "RESULT=%ERRORLEVEL%"
goto wait_exit
:missing_portable
echo Offline runtime is missing. Extract the entire Windows package again.
set "RESULT=1"
:wait_exit
if not defined LOCAL_RUN_NO_PAUSE pause
exit /b %RESULT%
