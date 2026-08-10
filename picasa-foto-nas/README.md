# Picasa Foto - Estrai su NAS

App con interfaccia grafica per Windows che sposta le foto scaricate da
Google Foto (file `.zip` nella cartella Download) dentro il NAS, in:

```
\\FS6706T-EC49\Picasa - Foto
```

## Cosa fa

1. Scegli manualmente il file `.zip` da estrarre (si apre già nella cartella Download).
2. Sfoglia le cartelle del NAS con **doppio click** sull'elenco per entrare
   dentro una sottocartella (anche più livelli, es. `antaeus` → `vacanze`).
   Usa "Su di un livello" per tornare indietro e "Nuova cartella qui..." per
   crearne una nuova esattamente nella posizione in cui ti trovi.
3. Premi "Estrai ZIP QUI": il contenuto dello zip viene copiato nella
   cartella in cui ti trovi in quel momento (mostrata sopra l'elenco).
4. Se l'estrazione va a buon fine, il file `.zip` originale viene cancellato
   dalla cartella Download.

Se il NAS non è raggiungibile o la cartella di destinazione non esiste,
l'app mostra un messaggio di errore e non tocca lo zip originale.

## Requisiti

- Windows con Python 3.8 o superiore installato (usa solo librerie incluse
  in Python: `tkinter`, `zipfile`, `os` — nessuna installazione aggiuntiva).
- Accesso di rete al NAS (`\\FS6706T-EC49\Picasa - Foto` deve essere
  raggiungibile, es. già mappato o visibile in Esplora File).

## Come si usa

Doppio click su `picasa_foto_app.py`, oppure da terminale:

```
python picasa_foto_app.py
```

## Cambiare il percorso del NAS

Se in futuro cambia il nome del NAS o della cartella condivisa, modifica la
riga `NAS_ROOT` all'inizio di `picasa_foto_app.py`:

```python
NAS_ROOT = r"\\FS6706T-EC49\Picasa - Foto"
```

## Creare un eseguibile .exe (opzionale)

Per non dover aprire un terminale ogni volta, puoi creare un `.exe` con
[PyInstaller](https://pyinstaller.org/):

```
pip install pyinstaller
pyinstaller --onefile --windowed picasa_foto_app.py
```

L'eseguibile verrà creato nella cartella `dist/`.
