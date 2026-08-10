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
import urllib.request
import webbrowser
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_file, render_template
from PIL import Image, UnidentifiedImageError

# Cartella del NAS da sfogliare. Modifica qui se cambia il nome del NAS
# o della cartella condivisa.
NAS_ROOT = Path(r"\\FS6706T-EC49\Picasa - Foto")

APP_ID = "picasa-foto-viewer"
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

app = Flask(__name__)


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
    return conn


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


def db_list_subfolders(rel):
    conn = get_db()
    rows = conn.execute(
        "SELECT path, name, "
        "EXISTS(SELECT 1 FROM folders c WHERE c.parent = folders.path) AS has_children "
        "FROM folders WHERE parent = ? ORDER BY name COLLATE NOCASE",
        (rel,),
    ).fetchall()
    conn.close()
    return [
        {"name": row["name"], "path": row["path"], "hasChildren": bool(row["has_children"])}
        for row in rows
    ]


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
def add_no_cache_headers(response):
    # Evita che il browser mostri una pagina/JS vecchi dopo un aggiornamento
    # dell'app: per una app locale a singolo utente il costo e' trascurabile.
    response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/")
def index():
    return render_template("index.html", root_label=NAS_ROOT.name)


@app.route("/api/ping")
def api_ping():
    return jsonify({"app": APP_ID})


@app.route("/api/tree")
def api_tree():
    rel = normalize_rel(request.args.get("path", ""))
    return jsonify(db_list_subfolders(rel))


@app.route("/api/photos")
def api_photos():
    rel = normalize_rel(request.args.get("path", ""))
    return jsonify(db_list_photos(rel))


@app.route("/api/reindex", methods=["POST"])
def api_reindex():
    if not NAS_ROOT.is_dir():
        return error_response(f"Impossibile raggiungere il NAS: {NAS_ROOT}", 503)
    rebuild_index()
    return jsonify({"ok": True})


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


# ---------------------------------------------------------------------------
# Avvio
# ---------------------------------------------------------------------------

def another_instance_running():
    """True se un'altra copia di questa app e' gia' in ascolto sulla porta."""
    try:
        with urllib.request.urlopen(f"http://{HOST}:{PORT}/api/ping", timeout=1) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("app") == APP_ID
    except Exception:
        return False


def main():
    url = f"http://{HOST}:{PORT}/"

    if another_instance_running():
        # L'app e' gia' aperta da un'altra finestra: non avviarne una
        # seconda (darebbe solo errori di porta occupata), apri solo il
        # browser sull'istanza gia' attiva.
        webbrowser.open(url)
        return

    if not NAS_ROOT.is_dir():
        print(f"ATTENZIONE: non trovo la cartella del NAS: {NAS_ROOT}")

    if not DB_PATH.exists() and NAS_ROOT.is_dir():
        print("Prima apertura: indicizzo le cartelle del NAS, un momento...")
        rebuild_index()
        print("Indice pronto.")

    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    app.run(host=HOST, port=PORT, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
