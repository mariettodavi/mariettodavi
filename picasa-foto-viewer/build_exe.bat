@echo off
cd /d %~dp0
echo Installo le librerie necessarie per compilare (solo la prima volta)...
python -m pip install --disable-pip-version-check -q -r requirements.txt pyinstaller
echo.
echo Creo PicasaFotoViewer.exe, un momento...
python -m PyInstaller --onefile --noconsole --name PicasaFotoViewer ^
  --add-data "templates;templates" --add-data "static;static" ^
  app.py
echo.
if exist "dist\PicasaFotoViewer.exe" (
  echo Fatto! Trovi PicasaFotoViewer.exe dentro la cartella "dist".
  echo Da ora puoi spostare/rinominare quel file dove vuoi e usarlo
  echo direttamente con un doppio click, senza bisogno di Python.
) else (
  echo Qualcosa e' andato storto durante la creazione dell'eseguibile.
  echo Controlla i messaggi sopra per capire cosa e' successo.
)
pause
