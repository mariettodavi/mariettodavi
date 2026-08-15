"""Visualizzatore locale delle foto del NAS (Picasa - Foto).

Mantiene un piccolo indice locale (SQLite) della struttura di cartelle e
foto del NAS, cosi' la navigazione e' istantanea invece di dover
interrogare il NAS via rete ad ogni click. L'indice viene creato al primo
avvio e poi aggiornato solo su richiesta (pulsante "Aggiorna" nell'app) o
automaticamente quando una cartella viene rinominata/spostata da qui.

Le miniature vengono generate la prima volta che servono e tenute in
cache su disco locale (thumb_cache/), mai sul NAS.
"""

import concurrent.futures
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from datetime import datetime
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_file, render_template
from PIL import Image, ImageDraw, UnidentifiedImageError

try:
    import pystray

    TRAY_AVAILABLE = True
except Exception:
    # Non solo ImportError: su alcuni sistemi l'inizializzazione del
    # backend dell'icona puo' fallire per altri motivi. In quel caso si
    # torna al comportamento precedente (niente icona nella barra) invece
    # di far crashare l'app all'avvio.
    TRAY_AVAILABLE = False

# Cartella del NAS da sfogliare. Modifica qui se cambia il nome del NAS
# o della cartella condivisa.
NAS_ROOT = Path(r"\\FS6706T-EC49\Picasa - Foto")

APP_ID = "picasa-foto-viewer"
# Aumenta questo numero ad ogni modifica: si vede in cima alla barra
# laterale dell'app, cosi' e' facile controllare se una build .exe e'
# davvero quella aggiornata invece di doverlo indovinare.
APP_VERSION = "2.21"
HOST = "127.0.0.1"
PORT = 8765

THUMB_SIZE = (320, 320)
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".wmv", ".3gp"}
MEDIA_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS
INVALID_FOLDER_CHARS = r'\/:*?"<>|'


def check_ffmpeg_available():
    """Vero se 'ffmpeg' e' installato e nel PATH: serve solo per generare
    le anteprime dei video (un fotogramma), non per riprodurli - la
    riproduzione nel browser non ha bisogno di ffmpeg."""
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
        return True
    except (OSError, subprocess.TimeoutExpired):
        return False


FFMPEG_AVAILABLE = check_ffmpeg_available()


def app_dir():
    """Cartella dove tenere i dati persistenti (cache, indice, config).

    NON e' la cartella del programma: quella cambia ad ogni aggiornamento
    (si scarica una cartella nuova, si ricompila l'exe in una nuova
    "dist"), quindi tenerci dentro i dati persistenti li fa perdere ad
    ogni aggiornamento. Si usa invece una cartella fissa nel profilo
    utente di Windows, che resta la stessa a prescindere da dove si trova
    il programma in quel momento.
    """
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home())
    else:
        base = str(Path.home())
    data_dir = Path(base) / "PicasaFotoViewer"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def legacy_app_dir():
    """Dove venivano tenuti i dati persistenti prima di questa versione
    (accanto al programma): serve solo per spostarli una volta sola."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def migrate_legacy_data():
    """Se ci sono ancora dati nella vecchia posizione (accanto al
    programma, da prima di questa versione), li sposta nella nuova
    cartella fissa, una volta sola: cosi' l'aggiornamento a questa
    versione non fa perdere l'indice, la cache o la configurazione."""
    old_dir = legacy_app_dir()
    new_dir = app_dir()
    if old_dir.resolve() == new_dir.resolve():
        return
    for name in ("config.json", "index.db", "thumb_cache", "perf.log"):
        old_path = old_dir / name
        new_path = new_dir / name
        if old_path.exists() and not new_path.exists():
            try:
                shutil.move(str(old_path), str(new_path))
            except OSError:
                pass


migrate_legacy_data()

CACHE_ROOT = app_dir() / "thumb_cache"
DB_PATH = app_dir() / "index.db"
# Configurazione locale (indirizzo e API key di Immich): NON viene mai
# pubblicata su GitHub, resta solo sul tuo PC in una cartella fissa che
# non cambia mai ad ogni aggiornamento. Vedi config.example.json per il
# formato.
CONFIG_PATH = app_dir() / "config.json"
# Quanto tempo impiega a leggere/ridurre ogni foto NUOVA (non quelle gia'
# in cache): utile per capire se la lentezza e' la rete verso il NAS o
# altro. Si puo' cancellare in ogni momento, si ricrea da sola.
PERF_LOG = app_dir() / "perf.log"

app = Flask(__name__)


def load_config():
    """Legge config.json. Ritorna (config, errore).

    errore e' None se il file non esiste (Immich semplicemente non e'
    configurato, va bene cosi') oppure se e' tutto ok; e' valorizzato solo
    se il file ESISTE ma non si riesce a leggerlo, cosi' l'errore arriva
    fino all'interfaccia invece di essere ignorato in silenzio.
    """
    defaults = {"immich_url": "", "immich_api_key": ""}
    if not CONFIG_PATH.exists():
        return defaults, None
    try:
        # utf-8-sig invece di utf-8: tollera il carattere invisibile (BOM)
        # che Blocco Note su Windows a volte mette all'inizio del file
        # quando lo salvi come "UTF-8", che altrimenti rompe il JSON.
        with open(CONFIG_PATH, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        return defaults, f"config.json presente ma non leggibile: {exc}"
    defaults.update({k: data.get(k, v) for k, v in defaults.items()})
    return defaults, None


# ---------------------------------------------------------------------------
# Indice locale (SQLite)
# ---------------------------------------------------------------------------

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE IF NOT EXISTS folders ("
        "path TEXT PRIMARY KEY, parent TEXT NOT NULL, name TEXT NOT NULL)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_folders_parent ON folders(parent)")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS photos ("
        "path TEXT PRIMARY KEY, folder TEXT NOT NULL, name TEXT NOT NULL)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_photos_folder ON photos(folder)")
    # Cartelle nascoste: scelta solo locale, non tocca il NAS e non viene
    # mai cancellata da un reindex.
    conn.execute("CREATE TABLE IF NOT EXISTS hidden_folders (path TEXT PRIMARY KEY)")
    # Nomi degli album gia' presenti su Immich (minuscolo, per confronto
    # case-insensitive), aggiornati insieme al resto quando premi "Aggiorna".
    conn.execute("CREATE TABLE IF NOT EXISTS immich_albums (name_lower TEXT PRIMARY KEY)")
    return conn


# Stato dell'ultimo tentativo di collegamento a Immich, mostrato nell'app
# cosi' non serve indovinare a distanza perche' i badge non compaiono.
# "checked" parte False e diventa True solo alla FINE del primo controllo:
# serve a distinguere "non ho ancora controllato" da "ho controllato ed e'
# andata male", altrimenti nei primi secondi dopo l'avvio (mentre il
# controllo gira ancora in background) l'interfaccia mostrava un falso
# "errore sconosciuto" solo perche' non c'era ancora stata risposta.
IMMICH_STATUS = {"configured": False, "ok": False, "error": None, "albumCount": 0, "checked": False}


def fetch_immich_album_names():
    """Scarica i nomi degli album da Immich.

    Ritorna (nomi, None) se va bene, oppure (None, messaggio_errore) —
    il messaggio serve a capire subito cosa non va, senza dover
    indovinare (config mancante, url sbagliato, chiave sbagliata, ecc.).
    """
    config, config_error = load_config()
    if config_error:
        return None, config_error
    url = config["immich_url"].strip().rstrip("/")
    api_key = config["immich_api_key"].strip()
    if not url or not api_key:
        return None, "config.json incompleto (serve sia immich_url che immich_api_key)"
    try:
        req = urllib.request.Request(
            f"{url}/api/albums", headers={"x-api-key": api_key, "Accept": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            albums = json.loads(resp.read().decode("utf-8"))
        if not isinstance(albums, list):
            return None, "risposta di Immich in un formato inatteso"
        names = set()
        for album in albums:
            name = album.get("albumName") or album.get("name")
            if name:
                names.add(name.strip().lower())
        return names, None
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            return None, "Immich ha rifiutato la API key (401, controlla config.json)"
        return None, f"Immich ha risposto con errore {exc.code}"
    except urllib.error.URLError as exc:
        return None, f"impossibile raggiungere {url}: {exc.reason}"
    except TimeoutError:
        return None, f"{url} non ha risposto in tempo (controlla indirizzo/porta)"
    except Exception as exc:
        return None, f"errore imprevisto: {exc}"


def refresh_immich_albums():
    """Aggiorna la tabella locale degli album Immich (bloccante: va chiamata
    sempre in un thread separato, vedi refresh_immich_albums_async)."""
    # "configured" significa "esiste un config.json da leggere": lo
    # mostriamo comunque anche se e' incompleto o rotto, cosi' l'errore
    # arriva a chi lo sta guardando invece di sparire nel nulla.
    IMMICH_STATUS["configured"] = CONFIG_PATH.exists()

    names, error = fetch_immich_album_names()
    if names is None:
        IMMICH_STATUS["ok"] = False
        IMMICH_STATUS["error"] = error
        IMMICH_STATUS["checked"] = True
        return False

    conn = get_db()
    with conn:
        conn.execute("DELETE FROM immich_albums")
        conn.executemany(
            "INSERT INTO immich_albums(name_lower) VALUES (?)", [(n,) for n in names]
        )
    conn.close()
    IMMICH_STATUS["ok"] = True
    IMMICH_STATUS["error"] = None
    IMMICH_STATUS["albumCount"] = len(names)
    IMMICH_STATUS["checked"] = True
    return True


def refresh_immich_albums_async():
    """Come refresh_immich_albums, ma in background: una Immich lenta o
    irraggiungibile non deve mai rallentare l'avvio dell'app o il pulsante
    Aggiorna (era proprio questo il bug che rallentava tutto)."""
    threading.Thread(target=refresh_immich_albums, daemon=True).start()


# Stato dell'ultima (ri)costruzione dell'indice, mostrato nell'interfaccia
# durante la primissima apertura: senza questo, mentre gira os.walk() su
# tutto il NAS (puo' richiedere ore su una libreria grande via rete) la
# pagina restava vuota senza dire perche', sembrando bloccata o rotta.
INDEX_STATUS = {"running": False}


def rebuild_index():
    """Rilegge tutto l'albero dal NAS e ricostruisce l'indice locale."""
    INDEX_STATUS["running"] = True
    try:
        conn = get_db()
        with conn:
            conn.execute("DELETE FROM folders")
            conn.execute("DELETE FROM photos")
            for dirpath, dirnames, filenames in os.walk(NAS_ROOT):
                dirnames.sort(key=str.lower)
                rel_dir = os.path.relpath(dirpath, NAS_ROOT)
                rel_dir = "" if rel_dir == "." else rel_dir.replace("\\", "/")
                for name in dirnames:
                    child_rel = f"{rel_dir}/{name}" if rel_dir else name
                    conn.execute(
                        "INSERT INTO folders(path, parent, name) VALUES (?, ?, ?)",
                        (child_rel, rel_dir, name),
                    )
                for name in filenames:
                    if Path(name).suffix.lower() in MEDIA_EXTENSIONS:
                        child_rel = f"{rel_dir}/{name}" if rel_dir else name
                        conn.execute(
                            "INSERT INTO photos(path, folder, name) VALUES (?, ?, ?)",
                            (child_rel, rel_dir, name),
                        )
        conn.close()
    finally:
        INDEX_STATUS["running"] = False


def folder_matches_immich_album(folder_name, immich_names_lower):
    """True se il nome della cartella corrisponde a un album Immich.

    Non deve essere per forza identico: molte cartelle hanno in fondo un
    suffisso in piu' (es. "Alessandra Teatro 2005" su Immich contro
    "Alessandra Teatro 2005 X" sul NAS), quindi basta che la cartella
    inizi con il nome dell'album.
    """
    name_lower = folder_name.strip().lower()
    for album in immich_names_lower:
        if name_lower == album or name_lower.startswith(album + " "):
            return True
    return False


def db_list_subfolders(rel, show_hidden=False):
    conn = get_db()
    rows = conn.execute(
        "SELECT path, name, "
        "EXISTS(SELECT 1 FROM folders c WHERE c.parent = folders.path) AS has_children, "
        "EXISTS(SELECT 1 FROM hidden_folders h WHERE h.path = folders.path) AS is_hidden, "
        "(SELECT COUNT(*) FROM photos p WHERE p.folder = folders.path) AS photo_count "
        "FROM folders WHERE parent = ? ORDER BY name COLLATE NOCASE",
        (rel,),
    ).fetchall()
    immich_names = [r["name_lower"] for r in conn.execute("SELECT name_lower FROM immich_albums")]
    conn.close()
    result = []
    for row in rows:
        if row["is_hidden"] and not show_hidden:
            continue
        result.append({
            "name": row["name"],
            "path": row["path"],
            "hasChildren": bool(row["has_children"]),
            "hidden": bool(row["is_hidden"]),
            "inImmich": folder_matches_immich_album(row["name"], immich_names),
            "photoCount": row["photo_count"],
        })
    return result


def db_list_photos(rel):
    conn = get_db()
    rows = conn.execute(
        "SELECT path, name FROM photos WHERE folder = ? ORDER BY name COLLATE NOCASE",
        (rel,),
    ).fetchall()
    conn.close()
    return [
        {
            "name": row["name"],
            "path": row["path"],
            "isVideo": Path(row["name"]).suffix.lower() in VIDEO_EXTENSIONS,
        }
        for row in rows
    ]


def db_rename_subtree(old_rel, new_rel):
    """Aggiorna l'indice dopo che una cartella e' stata rinominata/spostata,
    senza dover rileggere tutto il NAS da capo."""
    conn = get_db()
    with conn:
        folders = conn.execute(
            "SELECT path FROM folders WHERE path = ? OR path LIKE ?",
            (old_rel, old_rel + "/%"),
        ).fetchall()
        for row in folders:
            new_path = new_rel + row["path"][len(old_rel):]
            new_parent = os.path.dirname(new_path).replace("\\", "/")
            new_name = os.path.basename(new_path)
            conn.execute(
                "UPDATE folders SET path=?, parent=?, name=? WHERE path=?",
                (new_path, new_parent, new_name, row["path"]),
            )

        photos = conn.execute(
            "SELECT path, folder, name FROM photos WHERE folder = ? OR folder LIKE ?",
            (old_rel, old_rel + "/%"),
        ).fetchall()
        for row in photos:
            new_folder = new_rel + row["folder"][len(old_rel):]
            new_path = f"{new_folder}/{row['name']}" if new_folder else row["name"]
            conn.execute(
                "UPDATE photos SET path=?, folder=? WHERE path=?",
                (new_path, new_folder, row["path"]),
            )

        hidden = conn.execute(
            "SELECT path FROM hidden_folders WHERE path = ? OR path LIKE ?",
            (old_rel, old_rel + "/%"),
        ).fetchall()
        for row in hidden:
            new_path = new_rel + row["path"][len(old_rel):]
            conn.execute(
                "UPDATE hidden_folders SET path=? WHERE path=?", (new_path, row["path"])
            )
    conn.close()


def db_delete_subtree(rel):
    """Rimuove dall'indice locale una cartella e tutto cio' che contiene."""
    conn = get_db()
    with conn:
        conn.execute("DELETE FROM folders WHERE path = ? OR path LIKE ?", (rel, rel + "/%"))
        conn.execute("DELETE FROM photos WHERE folder = ? OR folder LIKE ?", (rel, rel + "/%"))
        conn.execute(
            "DELETE FROM hidden_folders WHERE path = ? OR path LIKE ?", (rel, rel + "/%")
        )
    conn.close()


# ---------------------------------------------------------------------------
# Accesso al filesystem del NAS
# ---------------------------------------------------------------------------

def normalize_rel(rel):
    """Valida un percorso relativo solo a livello di testo (nessun accesso
    al NAS): usato dagli endpoint che leggono dall'indice locale, cosi'
    sfogliare le cartelle non deve mai aspettare il NAS."""
    rel = (rel or "").strip().replace("\\", "/").strip("/")
    parts = [p for p in rel.split("/") if p]
    if any(p in ("..", ".") for p in parts):
        abort(400, "Percorso non valido")
    return "/".join(parts)


def safe_rel_path(rel):
    """Risolve un percorso relativo dentro NAS_ROOT, impedendo di uscirne.

    Usato solo dagli endpoint che devono davvero toccare il NAS (foto,
    miniature, rinomina, sposta).
    """
    rel = (rel or "").strip().replace("\\", "/")
    nas_resolved = NAS_ROOT.resolve()
    candidate = (nas_resolved / rel).resolve() if rel else nas_resolved
    if candidate != nas_resolved and nas_resolved not in candidate.parents:
        abort(400, "Percorso non valido")
    return candidate


def thumbnail_path_for(abs_source):
    rel = abs_source.resolve().relative_to(NAS_ROOT.resolve())
    return CACHE_ROOT / rel.parent / (rel.name + ".thumb.jpg")


def log_perf(line):
    try:
        with open(PERF_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def generate_image_thumbnail(abs_source, thumb_path):
    try:
        with Image.open(abs_source) as img:
            # draft: per i JPEG, fa decodificare al volo una versione gia'
            # ridotta invece di decodificare tutta la foto a piena
            # risoluzione solo per poi rimpicciolirla. Su foto di
            # smartphone (spesso 12+ megapixel) e' molte volte piu' veloce
            # ed e' pensato apposta per generare miniature.
            img.draft("RGB", THUMB_SIZE)
            img = img.convert("RGB")
            img.thumbnail(THUMB_SIZE)
            img.save(thumb_path, "JPEG", quality=85)
    except (UnidentifiedImageError, OSError):
        return False
    return True


def generate_video_thumbnail(abs_source, thumb_path):
    """Estrae un fotogramma dal video con ffmpeg e lo salva come
    miniatura. Prova al secondo 1 (evita spesso un primo fotogramma nero
    o sfocato); se il video e' piu' corto, riprova dal primissimo
    fotogramma invece di rinunciare subito."""
    if not FFMPEG_AVAILABLE:
        return False
    scale = f"scale={THUMB_SIZE[0]}:{THUMB_SIZE[1]}:force_original_aspect_ratio=decrease"
    for seek_args in (["-ss", "1"], []):
        try:
            result = subprocess.run(
                [
                    "ffmpeg", "-y", *seek_args, "-i", str(abs_source),
                    "-frames:v", "1", "-update", "1", "-vf", scale,
                    str(thumb_path),
                ],
                capture_output=True,
                timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        if result.returncode == 0 and thumb_path.exists():
            return True
    return False


def ensure_thumbnail(abs_source):
    thumb_path = thumbnail_path_for(abs_source)
    try:
        source_mtime = abs_source.stat().st_mtime
    except OSError:
        return None
    if thumb_path.exists() and thumb_path.stat().st_mtime >= source_mtime:
        return thumb_path
    thumb_path.parent.mkdir(parents=True, exist_ok=True)
    start = time.time()
    if abs_source.suffix.lower() in VIDEO_EXTENSIONS:
        ok = generate_video_thumbnail(abs_source, thumb_path)
    else:
        ok = generate_image_thumbnail(abs_source, thumb_path)
    if not ok:
        return None
    elapsed = time.time() - start
    try:
        size_kb = abs_source.stat().st_size / 1024
    except OSError:
        size_kb = -1
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_perf(f"{timestamp}  {elapsed:6.2f}s  {size_kb:8.0f} KB  {abs_source.name}")
    return thumb_path


# Stato della pre-generazione delle miniature in background, mostrato
# nell'app cosi' si vede il progresso invece di scoprirlo per caso.
PRECACHE_STATUS = {"running": False, "total": 0, "done": 0}
PRECACHE_LOCK = threading.Lock()
PRECACHE_WORKERS = 12  # librerie molto grandi impiegavano ore con solo 4


def precache_thumbnails_worker():
    if PRECACHE_STATUS["running"]:
        return  # gia' in corso, non farne partire un altro insieme
    conn = get_db()
    paths = [row["path"] for row in conn.execute("SELECT path FROM photos")]
    conn.close()

    with PRECACHE_LOCK:
        PRECACHE_STATUS["running"] = True
        PRECACHE_STATUS["total"] = len(paths)
        PRECACHE_STATUS["done"] = 0

    def process(rel):
        abs_source = (NAS_ROOT / rel).resolve()
        ensure_thumbnail(abs_source)
        with PRECACHE_LOCK:
            PRECACHE_STATUS["done"] += 1

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=PRECACHE_WORKERS) as ex:
            list(ex.map(process, paths))
    finally:
        with PRECACHE_LOCK:
            PRECACHE_STATUS["running"] = False


def precache_thumbnails_async():
    threading.Thread(target=precache_thumbnails_worker, daemon=True).start()


def error_response(message, status):
    return jsonify({"error": message}), status


def move_cache_dir(old_rel, new_rel):
    """Sposta la cache miniature insieme alla cartella, se esiste (best-effort)."""
    old_cache = CACHE_ROOT / old_rel
    if not old_cache.is_dir():
        return
    new_cache = CACHE_ROOT / new_rel
    try:
        new_cache.parent.mkdir(parents=True, exist_ok=True)
        old_cache.rename(new_cache)
    except OSError:
        pass


@app.after_request
def add_cache_headers(response):
    # La pagina e gli script/CSS non devono mai restare in cache nel
    # browser (altrimenti dopo un aggiornamento dell'app si rischia di
    # vedere ancora la versione vecchia). Le miniature e le foto invece
    # possono restare in cache tranquillamente: il browser le ritiene
    # valide finche' non cambia il percorso o la data di modifica del
    # file, quindi navigare avanti e indietro tra le stesse cartelle non
    # le ridownloada ogni volta dal server locale.
    if request.path.startswith("/api/thumb") or request.path.startswith("/api/full"):
        response.headers["Cache-Control"] = "private, max-age=3600"
    else:
        response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/")
def index():
    return render_template(
        "index.html",
        root_label=NAS_ROOT.name,
        app_version=APP_VERSION,
        ffmpeg_available=FFMPEG_AVAILABLE,
    )


@app.route("/api/ping")
def api_ping():
    return jsonify({"app": APP_ID, "version": APP_VERSION})


@app.route("/api/tree")
def api_tree():
    rel = normalize_rel(request.args.get("path", ""))
    show_hidden = request.args.get("showHidden") == "1"
    return jsonify(db_list_subfolders(rel, show_hidden))


@app.route("/api/photos")
def api_photos():
    rel = normalize_rel(request.args.get("path", ""))
    return jsonify(db_list_photos(rel))


@app.route("/api/reindex", methods=["POST"])
def api_reindex():
    if not NAS_ROOT.is_dir():
        return error_response(f"Impossibile raggiungere il NAS: {NAS_ROOT}", 503)
    rebuild_index()
    refresh_immich_albums_async()
    precache_thumbnails_async()
    return jsonify({"ok": True})


@app.route("/api/immich/status")
def api_immich_status():
    return jsonify(IMMICH_STATUS)


@app.route("/api/precache/status")
def api_precache_status():
    return jsonify(PRECACHE_STATUS)


@app.route("/api/index/status")
def api_index_status():
    return jsonify(INDEX_STATUS)


@app.route("/api/immich/albums")
def api_immich_albums_debug():
    """Elenco (in minuscolo) degli album letti da Immich, solo per
    verificare che i nomi coincidano davvero con quelli delle cartelle."""
    conn = get_db()
    rows = conn.execute("SELECT name_lower FROM immich_albums ORDER BY name_lower").fetchall()
    conn.close()
    return jsonify([row["name_lower"] for row in rows])


@app.route("/api/thumb")
def api_thumb():
    abs_source = safe_rel_path(request.args.get("path", ""))
    if not abs_source.is_file():
        abort(404)
    thumb_path = ensure_thumbnail(abs_source)
    if thumb_path is None:
        abort(415, "Impossibile generare la miniatura")
    return send_file(thumb_path, mimetype="image/jpeg")


@app.route("/api/full")
def api_full():
    abs_source = safe_rel_path(request.args.get("path", ""))
    if not abs_source.is_file():
        abort(404)
    return send_file(abs_source)


@app.route("/api/folder/rename", methods=["POST"])
def api_folder_rename():
    data = request.get_json(silent=True) or {}
    rel = (data.get("path") or "").strip()
    new_name = (data.get("newName") or "").strip()

    if not rel:
        return error_response("Non puoi rinominare la cartella principale", 400)
    if not new_name or any(ch in new_name for ch in INVALID_FOLDER_CHARS):
        return error_response(
            "Il nome della cartella non può essere vuoto o contenere: " + INVALID_FOLDER_CHARS,
            400,
        )

    abs_path = safe_rel_path(rel)
    if not abs_path.is_dir():
        return error_response("Cartella non trovata", 404)

    new_abs = abs_path.parent / new_name
    if new_abs.exists() and new_abs.resolve() != abs_path.resolve():
        return error_response("Esiste già una cartella con questo nome", 409)

    try:
        os.rename(abs_path, new_abs)
    except OSError as exc:
        return error_response(f"Impossibile rinominare: {exc}", 500)

    new_rel = os.path.relpath(new_abs, NAS_ROOT).replace("\\", "/")
    move_cache_dir(rel, new_rel)
    db_rename_subtree(rel, new_rel)
    return jsonify({"path": new_rel, "name": new_name})


@app.route("/api/folder/move", methods=["POST"])
def api_folder_move():
    data = request.get_json(silent=True) or {}
    rel = (data.get("path") or "").strip()
    dest_rel = (data.get("destPath") or "").strip()

    if not rel:
        return error_response("Non puoi spostare la cartella principale", 400)

    abs_path = safe_rel_path(rel)
    dest_abs = safe_rel_path(dest_rel)
    if not abs_path.is_dir():
        return error_response("Cartella non trovata", 404)
    if not dest_abs.is_dir():
        return error_response("Cartella di destinazione non trovata", 404)

    abs_resolved = abs_path.resolve()
    dest_resolved = dest_abs.resolve()
    if dest_resolved == abs_resolved or abs_resolved in dest_resolved.parents:
        return error_response("Non puoi spostare una cartella dentro se stessa", 400)
    if dest_resolved == abs_resolved.parent:
        return error_response("La cartella è già in questa posizione", 400)

    new_abs = dest_abs / abs_path.name
    if new_abs.exists():
        return error_response("Esiste già una cartella con questo nome nella destinazione", 409)

    try:
        shutil.move(str(abs_path), str(new_abs))
    except OSError as exc:
        return error_response(f"Impossibile spostare: {exc}", 500)

    new_rel = os.path.relpath(new_abs, NAS_ROOT).replace("\\", "/")
    move_cache_dir(rel, new_rel)
    db_rename_subtree(rel, new_rel)
    return jsonify({"path": new_rel})


@app.route("/api/folder/hide", methods=["POST"])
def api_folder_hide():
    data = request.get_json(silent=True) or {}
    rel = (data.get("path") or "").strip()
    if not rel:
        return error_response("Non puoi nascondere la cartella principale", 400)
    conn = get_db()
    with conn:
        conn.execute("INSERT OR IGNORE INTO hidden_folders(path) VALUES (?)", (rel,))
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/folder/unhide", methods=["POST"])
def api_folder_unhide():
    data = request.get_json(silent=True) or {}
    rel = (data.get("path") or "").strip()
    conn = get_db()
    with conn:
        conn.execute("DELETE FROM hidden_folders WHERE path = ?", (rel,))
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/folder/delete", methods=["POST"])
def api_folder_delete():
    """Elimina una cartella e tutto il suo contenuto DAVVERO dal NAS.

    Richiede che il nome della cartella venga ridigitato esattamente come
    conferma, per evitare cancellazioni accidentali: non e' recuperabile.
    """
    data = request.get_json(silent=True) or {}
    rel = (data.get("path") or "").strip()
    confirm_name = (data.get("confirmName") or "").strip()

    if not rel:
        return error_response("Non puoi eliminare la cartella principale", 400)

    abs_path = safe_rel_path(rel)
    if not abs_path.is_dir():
        return error_response("Cartella non trovata", 404)

    if confirm_name != abs_path.name:
        return error_response(
            "Il nome digitato non corrisponde al nome della cartella da eliminare", 400
        )

    try:
        shutil.rmtree(abs_path)
    except OSError as exc:
        return error_response(f"Impossibile eliminare: {exc}", 500)

    db_delete_subtree(rel)

    cache_dir = CACHE_ROOT / rel
    if cache_dir.is_dir():
        shutil.rmtree(cache_dir, ignore_errors=True)

    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Avvio
# ---------------------------------------------------------------------------

def running_instance_version():
    """Versione dell'istanza gia' in ascolto sulla porta, o None se non c'e'."""
    try:
        with urllib.request.urlopen(f"http://{HOST}:{PORT}/api/ping", timeout=1) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("app") == APP_ID:
                return data.get("version", "?")
    except Exception:
        pass
    return None


def show_blocking_message(title, message):
    """Mostra un messaggio anche senza console (l'exe usa --noconsole)."""
    try:
        import tkinter
        from tkinter import messagebox

        root = tkinter.Tk()
        root.withdraw()
        messagebox.showerror(title, message)
        root.destroy()
    except Exception:
        print(message)


def main():
    url = f"http://{HOST}:{PORT}/"

    running_version = running_instance_version()
    if running_version is not None:
        if running_version == APP_VERSION:
            # E' gia' aperta un'altra copia della STESSA versione: non
            # avviarne una seconda (darebbe solo errori di porta occupata),
            # apri solo il browser sull'istanza gia' attiva.
            webbrowser.open(url)
        else:
            # E' rimasta accesa in background una versione diversa (spesso
            # invisibile, senza finestra, se lanciata come .exe): meglio
            # avvisare chiaramente che far finta di niente e mostrare
            # sempre codice vecchio senza che nessuno se ne accorga.
            show_blocking_message(
                "Picasa Foto Viewer",
                "È rimasta accesa in background una versione precedente del programma "
                f"(v{running_version}, questa e' v{APP_VERSION}).\n\n"
                "Apri Gestione Attività (Ctrl+Shift+Esc), cerca \"PicasaFotoViewer.exe\" "
                "(o \"python.exe\" se stavi usando run.bat), terminala, poi riapri "
                "questo programma.",
            )
        return

    if not NAS_ROOT.is_dir():
        print(f"ATTENZIONE: non trovo la cartella del NAS: {NAS_ROOT}")

    if not DB_PATH.exists() and NAS_ROOT.is_dir():
        # Primissimo avvio in assoluto: anche qui NON blocchiamo piu'.
        # Prima il server partiva solo DOPO che tutta questa scansione del
        # NAS finiva: su una libreria grande, con un NAS lento in rete,
        # significava ore in cui il browser non aveva nemmeno un server
        # ad aspettarlo dall'altra parte (sembrava tutto bloccato/rotto,
        # non era ne' l'uno ne' l'altro). Il server parte subito, e la
        # sidebar mostra "Indicizzo..." finche' questa scansione in
        # sottofondo non e' finita (vedi INDEX_STATUS).
        print("Prima apertura: indicizzo le cartelle del NAS in sottofondo...")

        def first_index_then_precache():
            rebuild_index()
            precache_thumbnails_async()

        threading.Thread(target=first_index_then_precache, daemon=True).start()
    elif NAS_ROOT.is_dir():
        # Avvii successivi: l'indice di prima esiste gia', quindi il
        # browser puo' aprirsi subito con quello. In background lo
        # ricontrolliamo comunque contro il NAS, cosi' le cartelle
        # aggiunte da fuori (es. l'altra app che estrae gli zip di
        # Google Foto) compaiono da sole senza dover premere "Aggiorna" -
        # e solo DOPO che il ricontrollo e' finito parte anche il
        # precaricamento delle miniature, cosi' include anche le foto
        # appena trovate.
        def refresh_then_precache():
            rebuild_index()
            precache_thumbnails_worker()

        threading.Thread(target=refresh_then_precache, daemon=True).start()

    # In background: se Immich non e' configurato, e' lento o non e'
    # raggiungibile in questo momento, l'avvio dell'app non deve MAI
    # aspettarlo (era proprio questo il bug che rallentava tutto).
    refresh_immich_albums_async()

    threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    # threaded=True: senza, il server gestisce una richiesta alla volta,
    # quindi aprendo una cartella con tante foto le miniature venivano
    # generate in fila una dopo l'altra invece che in parallelo.
    if TRAY_AVAILABLE:
        # Il server gira in un thread "daemon": se l'icona nella barra
        # delle applicazioni viene chiusa (Esci), il processo termina
        # subito, niente resta acceso in background senza che si veda.
        server_thread = threading.Thread(
            target=lambda: app.run(host=HOST, port=PORT, debug=False, use_reloader=False, threaded=True),
            daemon=True,
        )
        server_thread.start()
        run_tray(url)
    else:
        app.run(host=HOST, port=PORT, debug=False, use_reloader=False, threaded=True)


def build_tray_icon_image():
    size = 64
    img = Image.new("RGB", (size, size), (15, 17, 21))
    draw = ImageDraw.Draw(img)
    draw.ellipse((6, 6, size - 6, size - 6), fill=(91, 140, 255))
    draw.ellipse((18, 18, size - 18, size - 18), fill=(15, 17, 21))
    return img


def run_tray(url):
    def on_open(icon, item):
        webbrowser.open(url)

    def on_quit(icon, item):
        icon.stop()
        # icon.stop() da solo a volte non basta a far tornare icon.run():
        # se qualcosa nella notifica di Windows resta appeso, il processo
        # (e il server Flask nel thread in background) restava vivo senza
        # finestra visibile. os._exit(0) chiude tutto, subito, senza
        # aspettare nessuno.
        os._exit(0)

    menu = pystray.Menu(
        pystray.MenuItem("Apri Picasa Foto Viewer", on_open, default=True),
        pystray.MenuItem("Esci", on_quit),
    )
    icon = pystray.Icon(APP_ID, build_tray_icon_image(), "Picasa Foto Viewer", menu)
    icon.run()


if __name__ == "__main__":
    main()
