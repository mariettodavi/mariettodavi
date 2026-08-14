# Picasa Foto Viewer

Piccola web app locale (stile vecchio Picasa Desktop) che legge le foto
direttamente dal NAS, in:

```
\\FS6706T-EC49\Picasa - Foto
```

e le mostra organizzate esattamente come sono sul NAS: a sinistra l'albero
di cartelle e sottocartelle (con accanto il numero di foto che contiene
ciascuna), a destra le miniature della cartella selezionata. Click su una
miniatura per aprirla ingrandita, con frecce (o tasti freccia della
tastiera) per scorrere le foto successive/precedenti.

## Precaricamento delle miniature in background

Appena l'app si avvia (e dopo ogni "↻ Aggiorna"), parte da sola in
sottofondo una scansione che genera le miniature mancanti di **tutta**
la libreria, non solo della cartella che stai guardando — così quando
apri davvero una cartella, nella maggior parte dei casi le miniature
sono già pronte invece di doverle generare lì per lì. Va a un ritmo
moderato (4 foto alla volta) apposta per non intasare il NAS mentre magari
stai già navigando.

Mentre è in corso vedi una riga tipo "Precaricamento miniature:
120/850" sotto "Mostra cartelle nascoste"; sparisce da sola quando ha
finito. Su una libreria grande la primissima volta può richiedere
diversi minuti in background (l'app resta comunque usabile nel
frattempo), le volte successive è molto più veloce perché deve
occuparsi solo delle foto nuove.

## Se una cartella è ancora lenta ad aprirsi

Se apri una cartella e non è ancora stata precaricata (o qualcosa
sembra fuori norma), l'app tiene un log con il tempo reale impiegato
per ogni foto: apri il file **`perf.log`** dentro
`%LOCALAPPDATA%\PicasaFotoViewer` con un editor di testo. Ogni riga
mostra quanto ci ha messo e quanto pesa il file originale — mandami
qualche riga se i tempi ti sembrano fuori norma, così capiamo se il
collo di bottiglia è la rete verso il NAS o altro. Il file si può
cancellare in qualsiasi momento, si ricrea da solo.

## Dove vive il programma (percorso fisso, sempre lo stesso)

Il programma vive **sempre e solo** in:

```
%USERPROFILE%\PicasaFotoViewer
```

Non spostarlo, non copiarlo in altre cartelle: se ci sono più copie in
giro (es. `Picasa - Claude`, `App - Picasa - Claude`, cartelle di zip
scaricati a mano) si crea solo confusione su quale sia "quella giusta".
`%USERPROFILE%\PicasaFotoViewer` è l'unica cartella che conta.

Per aprire e aggiornare il programma nella vita di tutti i giorni usa
**solo le due icone sul Desktop** (create automaticamente, vedi sotto):

- **"Picasa Foto Viewer"** → apre il programma
- **"Aggiorna Picasa Foto Viewer"** → lo aggiorna all'ultima versione

Non serve mai cercare file dentro le cartelle a mano.

## Prima installazione (una volta sola)

1. Scarica questo unico file:
   `https://raw.githubusercontent.com/mariettodavi/mariettodavi/claude/nuovo-progetto-foto-picasa-4d56p7/picasa-foto-viewer/aggiorna.bat`
   (salvalo dove preferisci, es. Download — la posizione da cui lo lanci
   non conta, perché installa sempre in `%USERPROFILE%\PicasaFotoViewer`).
2. Doppio click su quel file. Fa tutto da solo:
   - scarica l'ultima versione del programma da GitHub
   - la mette in `%USERPROFILE%\PicasaFotoViewer`
   - compila `PicasaFotoViewer.exe` (serve Python installato solo per
     questo passaggio, non per usare il programma dopo)
   - crea le due icone sul Desktop descritte sopra
3. Da quel momento, per aprire il programma usa sempre l'icona
   "Picasa Foto Viewer" sul Desktop.

Ogni passaggio termina sempre con un messaggio e "premi un tasto per
continuare", quindi la finestra non si chiude mai da sola senza farti
leggere cosa è successo.

## Come aggiornare a una versione nuova (procedura guidata)

Doppio click sull'icona **"Aggiorna Picasa Foto Viewer"** sul Desktop.
Fa tutto da solo, senza dover scaricare zip o copiare file a mano:

1. Chiude l'app se è aperta
2. Scarica l'ultima versione da GitHub
3. Sostituisce i file del programma con quelli nuovi (sempre dentro
   `%USERPROFILE%\PicasaFotoViewer`, mai altrove)
4. Ricompila `PicasaFotoViewer.exe`
5. Ricrea le icone sul Desktop (utile anche se le avessi cancellate per
   sbaglio)

Serve solo premere Invio un paio di volte quando richiesto. Serve una
connessione internet e Python già installato.

Indice, cache delle miniature e `config.json` **non stanno dentro
`%USERPROFILE%\PicasaFotoViewer`**: vivono in una cartella fissa a parte, nel tuo
profilo Windows (`%LOCALAPPDATA%\PicasaFotoViewer`), che l'aggiornamento
non tocca mai — quindi non li perdi né devi copiarli a mano da nessuna
parte.

**Nota una tantum**: se stai aggiornando da una versione precedente alla
2.17, la primissima volta che apri la nuova build l'app sposta da sola
(una volta sola) `config.json`, `index.db` e `thumb_cache` dalla vecchia
posizione (dentro `dist`) a quella nuova fissa — non serve fare nulla di
manuale, nemmeno stavolta.

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
locale (`index.db`, dentro `%LOCALAPPDATA%\PicasaFotoViewer`) con
l'elenco di cartelle e foto. Aprire le cartelle è quindi istantaneo.

- La **prima volta** che avvii l'app, o dopo aver cancellato `index.db`,
  viene creato leggendo tutto l'albero del NAS (può richiedere qualche
  secondo in più, una volta sola) — qui l'app aspetta prima di aprire il
  browser, perché non c'è ancora nulla da mostrare.
- **Ogni avvio successivo** ricontrolla il NAS da solo, in background,
  senza far aspettare l'apertura dell'app: se hai aggiunto cartelle o
  foto da fuori (es. con l'altra app che scompatta gli zip di Google
  Foto), compaiono da sole al riavvio, senza dover premere nulla. Su una
  libreria molto grande questo ricontrollo in background può richiedere
  qualche secondo: l'albero che vedi appena apri l'app potrebbe non
  includere ancora le aggiunte freschissime, ma compaiono da sole entro
  pochi secondi.
- Il pulsante **↻ Aggiorna** in alto a sinistra fa lo stesso controllo
  ma subito, senza dover chiudere e riaprire l'app.
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
verde ✓ accanto al nome della cartella. Il confronto non richiede un nome
identico al 100%: basta che il nome della cartella **inizi con** il nome
dell'album (maiuscole/minuscole ignorate), così funziona anche se la
cartella ha in fondo qualcosa in più rispetto all'album (es. album
"Alessandra Teatro 2005" su Immich → cartella "Alessandra Teatro 2005 X"
sul NAS: badge comunque visibile).

Per attivarlo:

1. Avvia l'app almeno una volta (crea da sola la cartella dove tiene i
   dati, vedi sotto), poi chiudila.
2. Apri Esplora File, scrivi nella barra dell'indirizzo
   `%LOCALAPPDATA%\PicasaFotoViewer` e premi Invio — ti porta dritto
   nella cartella giusta.
3. Copia lì dentro `config.example.json` (lo trovi nella cartella del
   progetto) e rinomina la copia in **`config.json`**.
4. Apri `config.json` e inserisci:
   - `immich_url`: l'indirizzo del tuo server Immich (es.
     `http://192.168.178.85:22283`).
   - `immich_api_key`: una API key generata da Immich (client web →
     avatar in alto a destra → Account Settings → API Keys → New API
     Key).
5. Riavvia l'app (o premi **↻ Aggiorna**) e i badge compaiono da soli.

`config.json` **non viene mai pubblicato su GitHub** (è escluso apposta,
vedi `.gitignore`) e non sta nella cartella del progetto: la tua API key
resta solo in quella cartella fissa sul tuo PC, al sicuro anche quando
aggiorni l'app. Il collegamento a Immich gira sempre in background: se
non è configurato, è lento o non è raggiungibile, l'app continua a
funzionare normalmente e non aspetta mai — semplicemente non compaiono
badge.

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
`%LOCALAPPDATA%\PicasaFotoViewer\thumb_cache\` (mai sul NAS: il NAS non
viene mai modificato). Le volte successive le miniature sono già pronte e
si aprono istantaneamente. Se una foto sul NAS viene modificata o
sostituita, l'app se ne accorge da sola e rigenera la sua miniatura.

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
