# Picasa Foto Viewer

Piccola web app locale (stile vecchio Picasa Desktop) che legge le foto
direttamente dal NAS, in:

```
\\FS6706T-EC49\Picasa - Foto
```

e le mostra organizzate esattamente come sono sul NAS: a sinistra l'albero
di cartelle e sottocartelle, a destra le miniature della cartella
selezionata. Click su una miniatura per aprirla ingrandita, con frecce
(o tasti freccia della tastiera) per scorrere le foto successive/precedenti.

## Come si usa (consigliato: un unico .exe, senza Python)

1. La prima volta, doppio click su `build_exe.bat`. Installa in automatico
   quello che serve e crea `PicasaFotoViewer.exe` dentro la cartella
   `dist`. Serve una volta sola (e serve Python installato solo per
   *creare* l'eseguibile, non per usarlo dopo).
2. Sposta `dist\PicasaFotoViewer.exe` dove preferisci (Desktop, una
   cartella qualsiasi) — è un file unico, autosufficiente.
3. Da quel momento, doppio click su `PicasaFotoViewer.exe` per aprire
   l'app: niente più Python, niente più "pip install" ad ogni avvio.

In alternativa, se preferisci non creare l'eseguibile, puoi continuare a
usare `run.bat` (richiede Python installato, vedi sotto).

## Se apri l'app mentre è già aperta

L'app se ne accorge da sola (controlla se c'è già un'altra copia in
ascolto) e si limita a riportarti alla finestra del browser già aperta,
invece di far partire un secondo programma che andrebbe in conflitto con
il primo. Se hai chiuso solo la scheda del browser per sbaglio, il
programma resta comunque acceso in background: aprendolo di nuovo ti
riporta semplicemente alla pagina.

Per chiudere davvero l'app, chiudi la finestra nera del programma (o,
con l'eseguibile `.exe`, usa Gestione Attività se non hai una finestra
visibile) prima di aggiornarla a una versione nuova.

## Velocità: l'indice locale

Invece di interrogare il NAS via rete ogni volta che apri una cartella
(lento se il NAS è lento a rispondere), l'app tiene un piccolo indice
locale (`index.db`, un file accanto al programma) con l'elenco di
cartelle e foto. Aprire le cartelle è quindi istantaneo.

- La **prima volta** che avvii l'app, o dopo aver cancellato `index.db`,
  viene creato leggendo tutto l'albero del NAS (può richiedere qualche
  secondo in più, una volta sola).
- Il pulsante **↻ Aggiorna** in alto a sinistra rilegge il NAS e
  aggiorna l'indice: usalo dopo aver aggiunto foto nuove da fuori
  dall'app (es. con l'altra app che scompatta gli zip di Google Foto).
- Rinominare/spostare una cartella dall'app stessa aggiorna l'indice da
  solo, senza bisogno di premere "Aggiorna".

## Rinominare e spostare le cartelle

Passando il mouse su una cartella nell'albero a sinistra compaiono due
icone:

- **✎ Rinomina** — chiede il nuovo nome e rinomina la cartella sul NAS.
- **⇒ Sposta...** — apre una finestra con l'albero delle cartelle: scegli
  la cartella di destinazione (o "Picasa - Foto (cartella principale)" per
  portarla al livello più alto) e premi "Sposta qui".

Queste operazioni agiscono direttamente sul NAS (spostano/rinominano le
cartelle vere, non una copia), quindi sono permanenti. L'app impedisce
operazioni non valide (es. spostare una cartella dentro se stessa) e
mostra un messaggio se qualcosa va storto (es. esiste già una cartella con
quel nome nella destinazione).

## Come funziona la cache delle miniature

La prima volta che apri una cartella, l'app genera le miniature delle foto
al suo interno e le salva in locale sul tuo PC, nella cartella
`thumb_cache/` accanto al programma (mai sul NAS: il NAS non viene mai
modificato). Le volte successive le miniature sono già pronte e si aprono
istantaneamente. Se una foto sul NAS viene modificata o sostituita, l'app
se ne accorge da sola e rigenera la sua miniatura.

## Requisiti

- Windows.
- Per creare l'eseguibile (`build_exe.bat`, una volta sola): Python 3.9+.
  Dopo, l'eseguibile non richiede più nulla.
- Per usare invece `run.bat` senza creare l'eseguibile: Python 3.9+
  installato sempre, con `Flask` e `Pillow` (installati in automatico da
  `run.bat`).
- Accesso di rete al NAS (`\\FS6706T-EC49\Picasa - Foto` deve essere
  raggiungibile).

L'app resta in ascolto solo sul tuo PC (`127.0.0.1`), non è raggiungibile
da altri dispositivi in rete.

## Cambiare il percorso del NAS

Se cambia il nome del NAS o della cartella condivisa, modifica la riga
`NAS_ROOT` all'inizio di `app.py` e ricrea l'eseguibile con
`build_exe.bat` (se lo usi):

```python
NAS_ROOT = Path(r"\\FS6706T-EC49\Picasa - Foto")
```

## Limiti attuali

- Mostra solo immagini (`.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.webp`,
  `.tiff`); eventuali video nelle cartelle vengono ignorati.
- Le foto in formato HEIC (tipico export iPhone) potrebbero non generare
  una miniatura se Pillow non ha il supporto HEIC installato: se ti serve,
  fammelo sapere e aggiungo il supporto.
- La griglia mostra solo le foto della cartella selezionata (non quelle
  delle sue sottocartelle insieme), esattamente come nel vecchio Picasa
  quando si sfoglia per cartella.
