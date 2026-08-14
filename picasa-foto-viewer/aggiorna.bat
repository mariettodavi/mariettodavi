@echo off
title Picasa Foto Viewer - Installazione/Aggiornamento

REM Cartella FISSA: il programma vive SEMPRE qui, qualunque sia la
REM cartella da cui lanci questo file (Desktop, Download, ovunque).
REM Cosi' non si creano piu' copie sparse in posti diversi e non si
REM perde mai il filo di "qual e' quella giusta".
REM E' dentro il profilo utente (non in C:\ direttamente) apposta:
REM ogni account Windows normale ha sempre il permesso di scrivere qui,
REM senza bisogno di "Esegui come amministratore".
set "TARGET_DIR=%USERPROFILE%\PicasaFotoViewer\"
set "ZIP_URL=https://github.com/mariettodavi/mariettodavi/archive/refs/heads/claude/nuovo-progetto-foto-picasa-4d56p7.zip"
set "WORK_DIR=%TEMP%\picasa_update_%RANDOM%"
set "ZIP_FILE=%WORK_DIR%\update.zip"
set "DESKTOP=%USERPROFILE%\Desktop"

echo ============================================
echo   Picasa Foto Viewer - Installazione/Aggiornamento
echo ============================================
echo.
echo Il programma vive sempre in: %TARGET_DIR%
echo (non importa da dove hai lanciato questo file)
echo.

echo [1/6] Chiudo l'app se e' in esecuzione...
taskkill /IM PicasaFotoViewer.exe /F >nul 2>&1

mkdir "%TARGET_DIR%" 2>nul
if not exist "%TARGET_DIR%" (
    echo.
    echo ============================================
    echo   ERRORE: non riesco a creare la cartella
    echo   %TARGET_DIR%
    echo ============================================
    echo Prova a fare click destro su questo file e scegliere
    echo "Esegui come amministratore", poi riprova.
    pause
    exit /b 1
)

mkdir "%WORK_DIR%" 2>nul

echo [2/6] Scarico l'ultima versione da GitHub...
powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue'; try { Invoke-WebRequest -Uri '%ZIP_URL%' -OutFile '%ZIP_FILE%' -UseBasicParsing } catch { exit 1 }"
if not exist "%ZIP_FILE%" (
    echo.
    echo ERRORE: il download non e' riuscito. Controlla la connessione internet e riprova.
    pause
    exit /b 1
)

echo [3/6] Estraggo i file scaricati...
powershell -NoProfile -Command "Expand-Archive -Path '%ZIP_FILE%' -DestinationPath '%WORK_DIR%\extracted' -Force"

set "SOURCE_DIR="
for /d %%D in ("%WORK_DIR%\extracted\*") do set "SOURCE_DIR=%%D\picasa-foto-viewer"

if not exist "%SOURCE_DIR%" (
    echo.
    echo ERRORE: non trovo la cartella picasa-foto-viewer nello zip scaricato.
    pause
    exit /b 1
)

echo [4/6] Controllo se ci sono dati da versioni vecchie da salvare prima di pulire...
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
REM non tocca mai se stesso mentre e' in esecuzione.
echo aggiorna.bat> "%WORK_DIR%\esclusi.txt"
REM TARGET_DIR finisce sempre con backslash (serve per tutti gli altri
REM usi tipo %TARGET_DIR%dist). Passarlo cosi' com'e', tra virgolette,
REM come destinazione di xcopy manda in confusione xcopy (backslash
REM subito prima della virgoletta di chiusura). Qui sotto si toglie
REM quell'ultimo carattere solo per questo comando, cosi' non c'e' nessun
REM backslash appena prima della virgoletta e xcopy non si confonde piu'.
set "TARGET_DIR_XCOPY=%TARGET_DIR:~0,-1%"
xcopy "%SOURCE_DIR%\*" "%TARGET_DIR_XCOPY%" /E /Y /I "/EXCLUDE:%WORK_DIR%\esclusi.txt" >nul

rmdir /s /q "%WORK_DIR%" 2>nul

if not exist "%TARGET_DIR%app.py" (
    echo.
    echo ============================================
    echo   ERRORE: la copia dei file non e' riuscita
    echo ============================================
    echo Non trovo app.py dentro %TARGET_DIR%
    echo Nessuna icona verra' creata/modificata sul Desktop.
    pause
    exit /b 1
)

echo [5/6] Ricompilo l'eseguibile (puo' richiedere qualche minuto)...
echo.
call "%TARGET_DIR%build_exe.bat"

if not exist "%TARGET_DIR%dist\PicasaFotoViewer.exe" (
    echo.
    echo ============================================
    echo   ERRORE: la compilazione non e' riuscita
    echo ============================================
    echo Non trovo PicasaFotoViewer.exe dentro %TARGET_DIR%dist
    echo.
    echo Motivo piu' probabile: Python non e' installato su questo PC
    echo ^(serve solo per compilare, non per usare il programma dopo^),
    echo oppure non e' stato trovato durante la compilazione.
    echo.
    echo Scorri in alto in questa finestra: se vedi scritte tipo
    echo "python non e' riconosciuto come comando interno o esterno",
    echo e' proprio questo. Manda quel testo a chi ti segue.
    echo.
    echo Le icone sul Desktop NON vengono toccate, per non lasciarle rotte.
    pause
    exit /b 1
)

echo [6/6] Sistemo le icone sul Desktop...
powershell -NoProfile -Command "$w = New-Object -ComObject WScript.Shell; $s1 = $w.CreateShortcut('%DESKTOP%\Picasa Foto Viewer.lnk'); $s1.TargetPath = '%TARGET_DIR%dist\PicasaFotoViewer.exe'; $s1.WorkingDirectory = '%TARGET_DIR%dist'; $s1.Save(); $s2 = $w.CreateShortcut('%DESKTOP%\Aggiorna Picasa Foto Viewer.lnk'); $s2.TargetPath = '%TARGET_DIR%aggiorna.bat'; $s2.WorkingDirectory = '%TARGET_DIR%'; $s2.Save()"

echo.
echo ============================================
echo   Fatto!
echo ============================================
echo.
echo Sul Desktop trovi ora due icone, usa sempre e solo quelle,
echo non cercare piu' file dentro le cartelle:
echo.
echo   - "Picasa Foto Viewer"           per APRIRE il programma
echo   - "Aggiorna Picasa Foto Viewer"  per AGGIORNARLO in futuro
echo.
echo (I tuoi dati - indice, miniature, configurazione Immich - sono al
echo  sicuro: non stanno in questa cartella, quindi non sono stati toccati.)
pause
