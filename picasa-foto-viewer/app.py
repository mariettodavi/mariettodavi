"""Visualizzatore locale delle foto del NAS (Picasa - Foto).

Legge cartelle e sottocartelle direttamente dal NAS, genera le miniature
la prima volta che servono e le tiene in cache su disco locale (in
thumb_cache/), cosi' le aperture successive sono immediate. La struttura
delle cartelle mostrata e' esattamente quella trovata sul NAS.
"""

import os
import shutil
import threading
import webbrowser
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_file, render_template
from PIL import Image, UnidentifiedImageError

# Cartella del NAS da sfogliare. Modifica qui se cambia il nome del NAS
# o della cartella condivisa.
NAS_ROOT = Path(r"\\FS6706T-EC49\Picasa - Foto")

# Cache locale delle miniature, salvata accanto a questo script.
CACHE_ROOT = Path(__file__).resolve().parent / "thumb_cache"

THUMB_SIZE = (320, 320)
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff"}
INVALID_FOLDER_CHARS = r'\/:*?"<>|'

HOST = "127.0.0.1"
PORT = 8765

app = Flask(__name__)


def safe_rel_path(rel):
    """Risolve un percorso relativo dentro NAS_ROOT, impedendo di uscirne."""
    rel = (rel or "").strip().replace("\\", "/")
    nas_resolved = NAS_ROOT.resolve()
    candidate = (nas_resolved / rel).resolve() if rel else nas_resolved
    if candidate != nas_resolved and nas_resolved not in candidate.parents:
        abort(400, "Percorso non valido")
    return candidate


def list_subfolders(abs_path):
    try:
        entries = sorted(
            (e for e in os.scandir(abs_path) if e.is_dir()),
            key=lambda e: e.name.lower(),
        )
    except OSError:
        return []
    result = []
    for entry in entries:
        has_children = False
        try:
            with os.scandir(entry.path) as it:
                has_children = any(e.is_dir() for e in it)
        except OSError:
            pass
        rel = os.path.relpath(entry.path, NAS_ROOT).replace("\\", "/")
        result.append({"name": entry.name, "path": rel, "hasChildren": has_children})
    return result


def list_photos(abs_path):
    try:
        entries = sorted(
            (
                e
                for e in os.scandir(abs_path)
                if e.is_file() and Path(e.name).suffix.lower() in IMAGE_EXTENSIONS
            ),
            key=lambda e: e.name.lower(),
        )
    except OSError:
        return []
    result = []
    for entry in entries:
        rel = os.path.relpath(entry.path, NAS_ROOT).replace("\\", "/")
        result.append({"name": entry.name, "path": rel})
    return result


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


@app.route("/")
def index():
    return render_template("index.html", root_label=NAS_ROOT.name)


@app.route("/api/tree")
def api_tree():
    abs_path = safe_rel_path(request.args.get("path", ""))
    return jsonify(list_subfolders(abs_path))


@app.route("/api/photos")
def api_photos():
    abs_path = safe_rel_path(request.args.get("path", ""))
    return jsonify(list_photos(abs_path))


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
    return jsonify({"path": new_rel})


def main():
    if not NAS_ROOT.is_dir():
        print(f"ATTENZIONE: non trovo la cartella del NAS: {NAS_ROOT}")
    url = f"http://{HOST}:{PORT}/"
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    app.run(host=HOST, port=PORT, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
