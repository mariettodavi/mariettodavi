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
`thumb_cache/` accanto ad `app.py` (mai sul NAS: il NAS non viene mai
modificato). Le volte successive le miniature sono già pronte e si aprono
istantaneamente. Se una foto sul NAS viene modificata o sostituita, l'app
se ne accorge da sola e rigenera la sua miniatura.

Le cartelle e le foto vengono sempre lette "al volo" dal NAS quando le
apri (non c'è un indice che deve scansionare tutto all'avvio), quindi
funziona bene sia con poche centinaia di foto sia con librerie molto
grandi.

## Requisiti

- Windows con Python 3.9 o superiore.
- Due librerie aggiuntive: `Flask` (per il piccolo server web locale) e
  `Pillow` (per generare le miniature). Vengono installate in automatico
  la prima volta che avvii `run.bat`.
- Accesso di rete al NAS (`\\FS6706T-EC49\Picasa - Foto` deve essere
  raggiungibile).

## Come si usa

Doppio click su `run.bat`. La prima volta installa le librerie necessarie
(serve qualche secondo), poi apre da solo il browser su
`http://127.0.0.1:8765`.

In alternativa, da terminale:

```
pip install -r requirements.txt
python app.py
```

L'app resta in ascolto solo sul tuo PC (`127.0.0.1`), non è raggiungibile
da altri dispositivi in rete.

## Cambiare il percorso del NAS

Se cambia il nome del NAS o della cartella condivisa, modifica la riga
`NAS_ROOT` all'inizio di `app.py`:

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
