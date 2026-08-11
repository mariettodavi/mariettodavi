"""Visualizzatore locale delle foto del NAS (Picasa - Foto).

Mantiene un piccolo indice locale (SQLite) della struttura di cartelle e
foto del NAS, cosi' la navigazione e' istantanea invece di dover
interrogare il NAS via rete ad ogni click. L'indice viene creato al primo
avvio e poi aggiornato solo su richiesta (pulsante "Aggiorna" nell'app) o
automaticamente quando una cartella viene rinominata/spostata da qui.

Le miniature vengono generate la prima volta che servono e tenute in
cache su disco locale (thumb_cache/), mai sul NAS.
"""

import json
import os
import shutil
import sqlite3
import sys
import threading
import urllib.error
import urllib.request
import webbrowser
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
APP_VERSION = "2.8"
HOST = "127.0.0.1"
PORT = 8765

THUMB_SIZE = (320, 320)
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff"}
INVALID_FOLDER_CHARS = r'\/:*?"<>|'


def app_dir():
    """Cartella dove tenere i dati persistenti (cache, indice).

    Quando l'app e' impacchettata come .exe con PyInstaller, i file
    accanto al modulo Python sono estratti in una cartella temporanea che
    sparisce ad ogni chiusura: i dati persistenti vanno quindi tenuti
    accanto all'eseguibile vero, non a quella cartella temporanea.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


CACHE_ROOT = app_dir() / "thumb_cache"
DB_PATH = app_dir() / "index.db"
# Configurazione locale (indirizzo e API key di Immich): NON viene mai
# pubblicata su GitHub, resta solo sul tuo PC accanto al programma. Vedi
# config.example.json per il formato.
CONFIG_PATH = app_dir() / "config.json"

app = Flask(__name__)


def load_config():
    defaults = {"immich_url": "", "immich_api_key": ""}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        defaults.update({k: data.get(k, v) for k, v in defaults.items()})
    except (OSError, json.JSONDecodeError):
        pass
    return defaults


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
IMMICH_STATUS = {"configured": False, "ok": False, "error": None, "albumCount": 0}


def fetch_immich_album_names():
    """Scarica i nomi degli album da Immich.

    Ritorna (nomi, None) se va bene, oppure (None, messaggio_errore) —
    il messaggio serve a capire subito cosa non va, senza dover
    indovinare (config mancante, url sbagliato, chiave sbagliata, ecc.).
    """
    config = load_config()
    url = config["immich_url"].strip().rstrip("/")
    api_key = config["immich_api_key"].strip()
    if not url or not api_key:
        return None, "config.json mancante o incompleto (serve immich_url e immich_api_key)"
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
    config = load_config()
    configured = bool(config["immich_url"].strip() and config["immich_api_key"].strip())
    IMMICH_STATUS["configured"] = configured

    names, error = fetch_immich_album_names()
    if names is None:
        IMMICH_STATUS["ok"] = False
        IMMICH_STATUS["error"] = error
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
    return True


def refresh_immich_albums_async():
    """Come refresh_immich_albums, ma in background: una Immich lenta o
    irraggiungibile non deve mai rallentare l'avvio dell'app o il pulsante
    Aggiorna (era proprio questo il bug che rallentava tutto)."""
    threading.Thread(target=refresh_immich_albums, daemon=True).start()


def rebuild_index():
    """Rilegge tutto l'albero dal NAS e ricostruisce l'indice locale."""
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
                if Path(name).suffix.lower() in IMAGE_EXTENSIONS:
                    child_rel = f"{rel_dir}/{name}" if rel_dir else name
                    conn.execute(
                        "INSERT INTO photos(path, folder, name) VALUES (?, ?, ?)",
                        (child_rel, rel_dir, name),
                    )
    conn.close()


def db_list_subfolders(rel, show_hidden=False):
    conn = get_db()
    rows = conn.execute(
        "SELECT path, name, "
        "EXISTS(SELECT 1 FROM folders c WHERE c.parent = folders.path) AS has_children, "
        "EXISTS(SELECT 1 FROM hidden_folders h WHERE h.path = folders.path) AS is_hidden, "
        "EXISTS(SELECT 1 FROM immich_albums a WHERE a.name_lower = LOWER(folders.name)) "
        "AS in_immich "
        "FROM folders WHERE parent = ? ORDER BY name COLLATE NOCASE",
        (rel,),
    ).fetchall()
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
            "inImmich": bool(row["in_immich"]),
        })
    return result


def db_list_photos(rel):
    conn = get_db()
    rows = conn.execute(
        "SELECT path, name FROM photos WHERE folder = ? ORDER BY name COLLATE NOCASE",
        (rel,),
    ).fetchall()
    conn.close()
    return [{"name": row["name"], "path": row["path"]} for row in rows]


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


def ensure_thumbnail(abs_source):
    thumb_path = thumbnail_path_for(abs_source)
    try:
        source_mtime = abs_source.stat().st_mtime
    except OSError:
        return None
    if thumb_path.exists() and thumb_path.stat().st_mtime >= source_mtime:
        return thumb_path
    thumb_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with Image.open(abs_source) as img:
            img = img.convert("RGB")
            img.thumbnail(THUMB_SIZE)
            img.save(thumb_path, "JPEG", quality=85)
    except (UnidentifiedImageError, OSError):
        return None
    return thumb_path


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
    return render_template("index.html", root_label=NAS_ROOT.name, app_version=APP_VERSION)


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
    return jsonify({"ok": True})


@app.route("/api/immich/status")
def api_immich_status():
    return jsonify(IMMICH_STATUS)


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
        print("Prima apertura: indicizzo le cartelle del NAS, un momento...")
        rebuild_index()
        print("Indice pronto.")

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

    menu = pystray.Menu(
        pystray.MenuItem("Apri Picasa Foto Viewer", on_open, default=True),
        pystray.MenuItem("Esci", on_quit),
    )
    icon = pystray.Icon(APP_ID, build_tray_icon_image(), "Picasa Foto Viewer", menu)
    icon.run()


if __name__ == "__main__":
    main()
