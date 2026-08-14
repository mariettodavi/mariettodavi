@echo off
setlocal enabledelayedexpansion
title Aggiornamento Picasa Foto Viewer

if "%~1"=="" (
    REM Prima esecuzione: si copia in una cartella temporanea e si
    REM rilancia da li'. Serve per poter sostituire in sicurezza anche
    REM questo stesso file dentro la cartella originale, senza che lo
    REM script stia "segando il ramo su cui e' seduto".
    set "ORIGINAL_DIR=%~dp0"
    set "SELF_COPY=%TEMP%\aggiorna_picasa_%RANDOM%.bat"
    copy /Y "%~f0" "!SELF_COPY!" >nul
    call "!SELF_COPY!" "!ORIGINAL_DIR!"
    exit /b
)

set "TARGET_DIR=%~1"
set "ZIP_URL=https://github.com/mariettodavi/mariettodavi/archive/refs/heads/claude/nuovo-progetto-foto-picasa-4d56p7.zip"
set "WORK_DIR=%TEMP%\picasa_update_%RANDOM%"
set "ZIP_FILE=%WORK_DIR%\update.zip"

echo ============================================
echo   Aggiornamento Picasa Foto Viewer
echo ============================================
echo.

echo [1/5] Chiudo l'app se e' in esecuzione...
taskkill /IM PicasaFotoViewer.exe /F >nul 2>&1

mkdir "%WORK_DIR%" 2>nul

echo [2/5] Scarico l'ultima versione da GitHub...
powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue'; try { Invoke-WebRequest -Uri '%ZIP_URL%' -OutFile '%ZIP_FILE%' -UseBasicParsing } catch { exit 1 }"
if not exist "%ZIP_FILE%" (
    echo.
    echo ERRORE: il download non e' riuscito. Controlla la connessione internet e riprova.
    pause
    exit /b 1
)

echo [3/5] Estraggo i file scaricati...
powershell -NoProfile -Command "Expand-Archive -Path '%ZIP_FILE%' -DestinationPath '%WORK_DIR%\extracted' -Force"

set "SOURCE_DIR="
for /d %%D in ("%WORK_DIR%\extracted\*") do set "SOURCE_DIR=%%D\picasa-foto-viewer"

if not exist "%SOURCE_DIR%" (
    echo.
    echo ERRORE: non trovo la cartella picasa-foto-viewer nello zip scaricato.
    echo Puo' darsi che il progetto sia stato rinominato: aggiornalo a mano per questa volta.
    pause
    exit /b 1
)

echo [4/5] Sostituisco i file del programma con quelli nuovi...
if exist "%TARGET_DIR%build" rmdir /s /q "%TARGET_DIR%build"
if exist "%TARGET_DIR%dist" rmdir /s /q "%TARGET_DIR%dist"
del /q "%TARGET_DIR%*.spec" >nul 2>&1
xcopy "%SOURCE_DIR%\*" "%TARGET_DIR%" /E /Y /I >nul

rmdir /s /q "%WORK_DIR%" 2>nul

echo [5/5] Ricompilo l'eseguibile (puo' richiedere qualche minuto)...
echo.
call "%TARGET_DIR%build_exe.bat"

echo.
echo ============================================
echo   Aggiornamento completato!
echo   Trovi il programma aggiornato in:
echo   %TARGET_DIR%dist\PicasaFotoViewer.exe
echo ============================================
echo.
echo (I tuoi dati - indice, miniature, configurazione Immich - sono al
echo  sicuro: non stanno in questa cartella, quindi non sono stati toccati.)
pause
