# Istruzioni permanenti per questo progetto

## Regola fondamentale: nessun aggiornamento deve mai far perdere dati utente

L'utente ha chiesto esplicitamente (e ribadito dopo un incidente reale) che
**ogni futuro aggiornamento o modifica a questo progetto deve preservare**:

- `config.json` (indirizzo e API key di Immich)
- `thumb_cache/` (le miniature già generate)
- `index.db` (l'indice di cartelle/foto)
- la sincronia dei badge Immich (`immich_albums` dentro `index.db`)

Dalla v2.17 questi dati vivono in `%LOCALAPPDATA%\PicasaFotoViewer`
(vedi `app_dir()` in `app.py`), **non** nella cartella del progetto. Questo
e' stato fatto apposta per rendere gli aggiornamenti sicuri per default.

## Cosa NON fare mai

- Non dare mai istruzioni (README, script, chat) che portino l'utente a
  cancellare `%LOCALAPPDATA%\PicasaFotoViewer` o il suo contenuto.
- Non scrivere script di build/aggiornamento che tocchino quella cartella.
- Attenzione alle istruzioni di "pulizia residui di build" (cancellare
  `build`/`dist`/`*.spec`): su versioni precedenti alla 2.17, `dist/`
  conteneva `config.json`/`index.db`/`thumb_cache` (i dati persistenti
  stavano accanto all'eseguibile). Se in futuro serve dare istruzioni di
  aggiornamento a qualcuno che potrebbe essere su una versione vecchia,
  avvisare esplicitamente di controllare/salvare prima quei file, oppure
  verificare la versione in uso prima di suggerire di cancellare `dist`.

## Incidente di riferimento (per non ripeterlo)

In una sessione precedente, l'utente e' stato guidato ad aggiornare da una
versione pre-2.17 seguendo la procedura "cancella build/dist come pulizia
residui" — ma su quella versione `dist/` conteneva ancora i dati veri
(config Immich, cache, indice), che sono stati persi. La migrazione
automatica (`migrate_legacy_data()` in `app.py`) esiste apposta per questi
casi, ma va eseguita PRIMA di cancellare la vecchia cartella `dist`, non
dopo. Qualunque istruzione di aggiornamento futura deve tenerne conto.

## Regola fondamentale #2: il programma vive in UN SOLO posto fisso

Prima di questa regola, `aggiorna.bat` operava nella cartella in cui si
trovava (`%~dp0`). Risultato reale: l'utente ha finito con il programma
sparso in piu' cartelle diverse (`Picasa - Claude`, `App - Picasa - Claude`,
cartelle di zip scaricati a mano...) senza piu' sapere quale fosse
"quella giusta", con perdita di ore a cercare file.

Da questa versione, `aggiorna.bat` usa un percorso **fisso e hardcoded**,
non relativo a se stesso: `C:\PicasaFotoViewer\`. Va lanciato da
qualunque posizione (Desktop, Download, ovunque) e installa/aggiorna
SEMPRE quella stessa cartella, mai una copia nuova altrove. Alla fine crea
anche due collegamenti sul Desktop ("Picasa Foto Viewer" per aprire,
"Aggiorna Picasa Foto Viewer" per aggiornare) cosi' l'utente non deve mai
piu' cercare file dentro le cartelle a mano.

**Non cambiare mai questo percorso fisso senza un motivo esplicito
dell'utente.** Se in futuro serve cambiarlo, va migrato con lo stesso
criterio di `migrate_legacy_data()`: mai lasciare l'utente a dover
cercare/spostare file a mano.
