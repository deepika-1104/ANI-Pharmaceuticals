@echo off
setlocal enabledelayedexpansion

title ANI-VOXA — Dev Launcher

echo.
echo  ============================================================
echo   ANI-VOXA  ^|  Starting Development Environment
echo  ============================================================
echo.

:: ── Locate project root ───────────────────────────────────────
set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "FRONTEND=%ROOT%frontend"

:: ── Sanity checks ─────────────────────────────────────────────
if not exist "%BACKEND%\main.py" (
    echo  [ERROR] backend\main.py not found.
    echo          Run this script from the project root folder.
    pause & exit /b 1
)

if not exist "%FRONTEND%\package.json" (
    echo  [ERROR] frontend\package.json not found.
    pause & exit /b 1
)

if not exist "%BACKEND%\.env" (
    echo  [WARN]  backend\.env not found.
    echo          Copy backend\.env.example to backend\.env and
    echo          set LLM_API_KEY and MONGO_URI before starting.
    echo.
    pause & exit /b 1
)

:: ── Install frontend deps if missing ──────────────────────────
if not exist "%FRONTEND%\node_modules" (
    echo  [INFO]  node_modules missing - running npm install ...
    pushd "%FRONTEND%"
    call npm install
    if errorlevel 1 (
        echo  [ERROR] npm install failed.
        pause & exit /b 1
    )
    popd
    echo.
)

:: ── Free port 8000 if already in use ─────────────────────────
echo  [INFO]  Checking port 8000 ...
netstat -ano | findstr ":8000 " | findstr "LISTENING" > "%TEMP%\voxa_port.txt"
FOR /F "tokens=5" %%P IN (%TEMP%\voxa_port.txt) DO (
    echo  [INFO]  Killing existing process on port 8000 ^(PID: %%P^) ...
    taskkill /PID %%P /F >nul 2>&1
)
del "%TEMP%\voxa_port.txt" >nul 2>&1

:: ── Write temp launcher scripts (avoids all quoting issues) ───
set "TMPB=%TEMP%\voxa_backend.bat"
set "TMPF=%TEMP%\voxa_frontend.bat"

(
    echo @echo off
    echo title ANI-VOXA Backend
    echo cd /d "%BACKEND%"
    echo echo.
    echo echo  ANI-VOXA Backend starting on http://localhost:8000
    echo echo  Press Ctrl+C to stop.
    echo echo.
    echo python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
    echo pause
) > "%TMPB%"

(
    echo @echo off
    echo title ANI-VOXA Frontend
    echo cd /d "%FRONTEND%"
    echo echo.
    echo echo  ANI-VOXA Frontend starting on http://localhost:5173
    echo echo  Press Ctrl+C to stop.
    echo echo.
    echo npm run dev
    echo pause
) > "%TMPF%"

:: ── Launch backend ────────────────────────────────────────────
echo  [INFO]  Starting backend  ...
start "ANI-VOXA Backend"  cmd /k "%TMPB%"

timeout /t 3 /nobreak >nul

:: ── Launch frontend ───────────────────────────────────────────
echo  [INFO]  Starting frontend ...
start "ANI-VOXA Frontend" cmd /k "%TMPF%"

timeout /t 2 /nobreak >nul

:: ── Status monitor — stays open until Ctrl+C ─────────────────
:monitor
cls
echo.
echo  ============================================================
echo   ANI-VOXA  ^|  Services Running
echo  ============================================================
echo.
echo   Backend   :  http://localhost:8000
echo   Frontend  :  http://localhost:5173
echo   API docs  :  http://localhost:8000/docs
echo   Health    :  http://localhost:8000/api/health
echo.
echo  ============================================================
echo.
echo   Services are running in their own windows.
echo   Press Enter in this window to stop everything.
echo.
pause >nul
goto cleanup

:: ── Cleanup on Ctrl+C ─────────────────────────────────────────
:cleanup
echo.
echo  [INFO]  Stopping all ANI-VOXA services ...
taskkill /fi "WINDOWTITLE eq ANI-VOXA Backend*"  /t /f >nul 2>&1
taskkill /fi "WINDOWTITLE eq ANI-VOXA Frontend*" /t /f >nul 2>&1
del "%TMPB%" >nul 2>&1
del "%TMPF%" >nul 2>&1
echo  [INFO]  Done.
endlocal
