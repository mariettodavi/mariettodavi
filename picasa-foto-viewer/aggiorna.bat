@echo off
title Aggiornamento Picasa Foto Viewer

set "TARGET_DIR=%~dp0"
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
    echo Se il problema persiste, aggiorna a mano seguendo le istruzioni nel README.
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
    echo Aggiorna a mano per questa volta seguendo le istruzioni nel README.
    pause
    exit /b 1
)

echo [4/5] Controllo se ci sono dati da versioni vecchie da salvare prima di pulire...
set "OLD_DIST=%TARGET_DIR%dist"
set "NEW_DATA_DIR=%LOCALAPPDATA%\PicasaFotoViewer"
if exist "%OLD_DIST%\config.json" if not exist "%NEW_DATA_DIR%\config.json" (
    mkdir "%NEW_DATA_DIR%" 2>nul
    move "%OLD_DIST%\config.json" "%NEW_DATA_DIR%\config.json" >nul
    echo   - trovato e salvato config.json da una versione precedente
)
if exist "%OLD_DIST%\index.db" if not exist "%NEW_DATA_DIR%\index.db" (
    mkdir "%NEW_DATA_DIR%" 2>nul
    move "%OLD_DIST%\index.db" "%NEW_DATA_DIR%\index.db" >nul
    echo   - trovato e salvato index.db da una versione precedente
)
if exist "%OLD_DIST%\thumb_cache" if not exist "%NEW_DATA_DIR%\thumb_cache" (
    mkdir "%NEW_DATA_DIR%" 2>nul
    move "%OLD_DIST%\thumb_cache" "%NEW_DATA_DIR%\thumb_cache" >nul
    echo   - trovata e salvata la cache miniature da una versione precedente
)
if exist "%OLD_DIST%\perf.log" if not exist "%NEW_DATA_DIR%\perf.log" (
    mkdir "%NEW_DATA_DIR%" 2>nul
    move "%OLD_DIST%\perf.log" "%NEW_DATA_DIR%\perf.log" >nul
)

echo Sostituisco i file del programma con quelli nuovi...
if exist "%TARGET_DIR%build" rmdir /s /q "%TARGET_DIR%build"
if exist "%TARGET_DIR%dist" rmdir /s /q "%TARGET_DIR%dist"
del /q "%TARGET_DIR%*.spec" >nul 2>&1

REM Questo file (aggiorna.bat) viene escluso apposta dalla sostituzione:
REM non tocca mai se stesso mentre e' in esecuzione. Se in futuro esce
REM una versione nuova di aggiorna.bat, va aggiornata a mano una volta
REM (scaricando di nuovo solo questo file), poi torna ad aggiornarsi da
REM solo per tutto il resto.
echo aggiorna.bat> "%WORK_DIR%\esclusi.txt"
xcopy "%SOURCE_DIR%\*" "%TARGET_DIR%" /E /Y /I "/EXCLUDE:%WORK_DIR%\esclusi.txt" >nul

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
