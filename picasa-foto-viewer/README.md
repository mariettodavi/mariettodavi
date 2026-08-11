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

## Come chiudere l'app

L'app non ha una finestra normale (per non tenere in giro una console
brutta), ma mentre è accesa mostra un'**icona nella barra delle
applicazioni** (in basso a destra, vicino all'orologio — se non la vedi
subito, controlla la freccetta "icone nascoste"). Click destro su
quell'icona → **Esci** per chiuderla davvero.

Chiudere solo la scheda del browser NON chiude l'app: resta accesa in
background (comodo, così la riapri istantaneamente), ma se vuoi
davvero spegnerla — ad esempio prima di installare una versione nuova —
usa "Esci" dall'icona nella barra.

Se stai ancora usando `run.bat` invece dell'eseguibile, quello mostra
una normale finestra nera: chiudi quella.

## Se apri l'app mentre è già aperta

L'app se ne accorge da sola (controlla se c'è già un'altra copia in
ascolto) e si limita a riportarti alla finestra del browser già aperta,
invece di far partire un secondo programma che andrebbe in conflitto con
il primo. Se invece rileva una **versione diversa** già accesa in
background, te lo dice con un messaggio chiaro invece di aprirsi in
silenzio sulla copia vecchia — a quel punto usa "Esci" dall'icona nella
barra (vedi sopra) e riprova.

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

## Rinominare, spostare, nascondere ed eliminare le cartelle

Passando il mouse su una cartella nell'albero a sinistra compaiono
quattro icone:

- **✎ Rinomina** — chiede il nuovo nome e rinomina la cartella sul NAS.
- **⇒ Sposta...** — apre una finestra con l'albero delle cartelle: scegli
  la cartella di destinazione (o "Picasa - Foto (cartella principale)" per
  portarla al livello più alto) e premi "Sposta qui".
- **👁 Nascondi** — fa sparire la cartella dall'albero, ma **non tocca
  nulla sul NAS**: è una scelta solo dell'app, reversibile in qualsiasi
  momento. Per rivederla (e per farla ricomparire), spunta "Mostra
  cartelle nascoste" in alto nella barra laterale: le cartelle nascoste
  compaiono in corsivo, con l'icona che diventa "Mostra" per farle
  tornare visibili normalmente.
- **🗑 Elimina** — cancella per sempre la cartella e tutto il suo
  contenuto **dal NAS**. Non è recuperabile: l'app chiede di riscrivere
  esattamente il nome della cartella prima di abilitare il pulsante di
  conferma, apposta per evitare click accidentali.

Rinomina e sposta agiscono direttamente sul NAS (sono operazioni vere,
non su una copia), quindi sono permanenti. L'app impedisce operazioni
non valide (es. spostare una cartella dentro se stessa) e mostra un
messaggio se qualcosa va storto (es. esiste già una cartella con quel
nome nella destinazione).

## Badge "già su Immich"

Se alcune cartelle sono già state caricate come album su un server
[Immich](https://immich.app/), l'app può mostrare un piccolo pallino
verde ✓ accanto al nome della cartella quando esiste un album con lo
stesso nome (confronto senza distinguere maiuscole/minuscole).

Per attivarlo:

1. Copia `config.example.json` e rinomina la copia in **`config.json`**
   (stessa cartella di `app.py`).
2. Apri `config.json` e inserisci:
   - `immich_url`: l'indirizzo del tuo server Immich (es.
     `http://192.168.178.85:22283`).
   - `immich_api_key`: una API key generata da Immich (client web →
     avatar in alto a destra → Account Settings → API Keys → New API
     Key).
3. Riavvia l'app (o premi **↻ Aggiorna**) e i badge compaiono da soli.

`config.json` **non viene mai pubblicato su GitHub** (è escluso apposta,
vedi `.gitignore`): la tua API key resta solo sul tuo PC. Il collegamento
a Immich gira sempre in background: se non è configurato, è lento o non
è raggiungibile, l'app continua a funzionare normalmente e non aspetta
mai — semplicemente non compaiono badge.

Sotto "Mostra cartelle nascoste" compare una riga di stato che dice
esattamente cosa succede: **"Immich: N album trovati"** (verde) se va
tutto bene, oppure il motivo preciso se qualcosa non va (es. API key
sbagliata, indirizzo non raggiungibile) — utile per capire subito cosa
correggere in `config.json` senza doverlo indovinare.

I badge si aggiornano insieme all'indice: premi **↻ Aggiorna** dopo aver
creato un nuovo album su Immich per vederlo comparire.

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
- L'icona nella barra delle applicazioni richiede Windows; se per qualche
  motivo non riesce a crearla, l'app funziona comunque ma senza icona (in
  quel caso l'unico modo per chiuderla resta Gestione Attività).
