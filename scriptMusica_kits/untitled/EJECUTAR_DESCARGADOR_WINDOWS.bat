@echo off
setlocal EnableExtensions

cd /d "%~dp0"

set "MIN_PYTHON_MAJOR=3"
set "MIN_PYTHON_MINOR=10"
set "PYTHON_INSTALL_VERSION=3.12.10"
set "PYTHON_INSTALLER=%TEMP%\python-%PYTHON_INSTALL_VERSION%-amd64.exe"
set "PYTHON_INSTALLER_URL=https://www.python.org/ftp/python/%PYTHON_INSTALL_VERSION%/python-%PYTHON_INSTALL_VERSION%-amd64.exe"

echo ====================================================================
echo  DESCARGADOR DE AUDIO - YOUTUBE / SOUNDCLOUD / BANDCAMP / RAVEYARD
echo ====================================================================
echo  Uso permitido: musica propia, libre, Creative Commons o con permiso.
echo ====================================================================
echo.

call :DetectPython

if not defined PYTHON_CMD (
    echo No se encontro Python %MIN_PYTHON_MAJOR%.%MIN_PYTHON_MINOR% o superior.
    call :InstallPython
    if errorlevel 1 goto :Fatal
    call :DetectPython
)

if not defined PYTHON_CMD (
    echo [ERROR] Python se instalo, pero este instalador no pudo detectarlo.
    echo Cierra esta ventana y vuelve a abrir EJECUTAR_DESCARGADOR_WINDOWS.bat.
    goto :Fatal
)

echo Python detectado:
%PYTHON_CMD% --version

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info >= (%MIN_PYTHON_MAJOR%, %MIN_PYTHON_MINOR%) else 1)" >nul 2>nul
    if errorlevel 1 (
        echo.
        echo El entorno virtual existente usa una version antigua de Python.
        echo Se creara uno nuevo.
        rmdir /s /q ".venv"
    )
)

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo Creando entorno virtual de Python...
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] No se pudo crear el entorno virtual.
        goto :Fatal
    )
)

set "VENV_PY=.venv\Scripts\python.exe"

echo.
echo Preparando pip...
"%VENV_PY%" -m ensurepip --upgrade >nul 2>nul
"%VENV_PY%" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 (
    echo [ERROR] No se pudo preparar pip.
    goto :Fatal
)

echo.
echo Instalando / actualizando dependencias del descargador...
if exist "requirements.txt" (
    "%VENV_PY%" -m pip install --upgrade -r requirements.txt
) else (
    "%VENV_PY%" -m pip install --upgrade "yt-dlp[default]" imageio-ffmpeg
)
if errorlevel 1 (
    echo [ERROR] No se pudieron instalar las dependencias.
    echo Verifica tu conexion a internet y vuelve a ejecutar este archivo.
    goto :Fatal
)

echo.
echo Verificando dependencias...
"%VENV_PY%" -c "import yt_dlp, imageio_ffmpeg; print('yt-dlp OK'); print('FFmpeg local OK:', imageio_ffmpeg.get_ffmpeg_exe())"
if errorlevel 1 (
    echo [ERROR] La verificacion de dependencias fallo.
    goto :Fatal
)

echo.
echo Abriendo descargador...
echo.
"%VENV_PY%" descargar.py

echo.
pause
exit /b 0

:DetectPython
set "PYTHON_CMD="

where py >nul 2>nul
if not errorlevel 1 (
    py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (%MIN_PYTHON_MAJOR%, %MIN_PYTHON_MINOR%) else 1)" >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=py -3"
)

if not defined PYTHON_CMD (
    for %%P in (
        "%LocalAppData%\Programs\Python\Python313\python.exe"
        "%LocalAppData%\Programs\Python\Python312\python.exe"
        "%LocalAppData%\Programs\Python\Python311\python.exe"
        "%LocalAppData%\Programs\Python\Python310\python.exe"
    ) do (
        if not defined PYTHON_CMD (
            if exist "%%~fP" (
                "%%~fP" -c "import sys; raise SystemExit(0 if sys.version_info >= (%MIN_PYTHON_MAJOR%, %MIN_PYTHON_MINOR%) else 1)" >nul 2>nul
                if not errorlevel 1 set "PYTHON_CMD="%%~fP""
            )
        )
    )
)

if not defined PYTHON_CMD (
    where python >nul 2>nul
    if not errorlevel 1 (
        python -c "import sys; raise SystemExit(0 if sys.version_info >= (%MIN_PYTHON_MAJOR%, %MIN_PYTHON_MINOR%) else 1)" >nul 2>nul
        if not errorlevel 1 set "PYTHON_CMD=python"
    )
)

exit /b 0

:InstallPython
echo.
echo Intentando instalar Python automaticamente...

where winget >nul 2>nul
if not errorlevel 1 (
    echo Instalando Python con winget...
    winget install --id Python.Python.3.12 --exact --accept-package-agreements --accept-source-agreements --disable-interactivity
    if not errorlevel 1 exit /b 0

    echo winget no pudo instalar Python 3.12. Se intentara descarga directa desde python.org.
) else (
    echo winget no esta disponible. Se intentara descarga directa desde python.org.
)

echo Descargando instalador de Python %PYTHON_INSTALL_VERSION%...
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%PYTHON_INSTALLER_URL%' -OutFile '%PYTHON_INSTALLER%' -UseBasicParsing; exit 0 } catch { Write-Host $_; exit 1 }"
if errorlevel 1 (
    echo [ERROR] No se pudo descargar Python.
    echo Instala Python manualmente desde https://www.python.org/downloads/windows/
    echo Marca la opcion Add python.exe to PATH y vuelve a ejecutar este .bat.
    exit /b 1
)

echo Instalando Python para este usuario...
"%PYTHON_INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1 Include_pip=1 Include_test=0 Shortcuts=0
if errorlevel 1 (
    echo [ERROR] El instalador de Python fallo.
    exit /b 1
)

exit /b 0

:Fatal
echo.
echo Instalacion incompleta. Revisa los mensajes anteriores.
echo.
pause
exit /b 1
