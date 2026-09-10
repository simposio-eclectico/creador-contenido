#!/usr/bin/env python3
"""
server.py - Flask web server para orquestar el pipeline creador-contenido.

Permite desde una interfaz web:
1. Seleccionar una carpeta de fotos/metadata.
2. Pegar la letra (frases).
3. Elegir formato y opciones.
4. El servidor automáticamente:
   - Detecta si la carpeta tiene metadata.json.
   - Si no, corre generate_from_folder.py primero.
   - Encadena automáticamente a main.py.
5. Muestra un log en vivo y al terminar permite descargar/ver el review.html.
"""
import json
import subprocess
import sys
import threading
import uuid
from pathlib import Path
from typing import Dict, Optional

from flask import Flask, jsonify, render_template, request, send_from_directory

PROJECT_ROOT = Path(__file__).resolve().parent
JOBS_DIR = PROJECT_ROOT / "jobs"
JOBS_DIR.mkdir(exist_ok=True)

app = Flask(__name__, template_folder="templates", static_folder="static", static_url_path="/static")

JOBS: Dict[str, Dict] = {}
JOBS_LOCK = threading.Lock()


def get_job(job_id: str) -> Optional[Dict]:
    with JOBS_LOCK:
        return JOBS.get(job_id)


def update_job(job_id: str, **kwargs):
    with JOBS_LOCK:
        if job_id in JOBS:
            JOBS[job_id].update(kwargs)


def read_log_tail(log_path: Path, lines: int = 50) -> str:
    """Lee las últimas N líneas de un archivo de log."""
    if not log_path.exists():
        return ""
    try:
        content = log_path.read_text(encoding="utf-8", errors="replace")
        lines_list = content.splitlines()
        return "\n".join(lines_list[-lines:])
    except Exception:
        return ""


def run_job(job_id: str, params: dict):
    """Ejecuta el pipeline (generate si falta metadata, luego main) en un hilo de fondo."""
    job = get_job(job_id)
    job_dir = JOBS_DIR / job_id
    log_path = job_dir / "log.txt"

    def log_write(msg: str, end="\n"):
        """Escribe a log.txt de forma thread-safe."""
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(msg + end)

    try:
        # Validaciones finales (por si acaso cambiaron cosas entre submit y aquí)
        folder = Path(params["folder"]).expanduser().resolve()
        if not folder.exists():
            update_job(job_id, status="error", error=f"Carpeta no existe: {folder}")
            return
        if not folder.is_dir():
            update_job(job_id, status="error", error=f"No es una carpeta: {folder}")
            return

        # Decide si necesita step de generación
        metadata_path = folder / "metadata.json"
        if metadata_path.exists():
            log_write("✓ Carpeta ya tiene metadata.json, saltando generate_from_folder.py")
            images_dir = folder
        else:
            log_write("✗ No encontré metadata.json, procesando carpeta de fotos...")
            log_write("")
            update_job(job_id, status="running_generate", stage="Procesando carpeta de fotos")

            generate_output = params.get("generate_output")
            if not generate_output:
                generate_output = f"{folder}_procesado"
            generate_output = Path(generate_output).expanduser().resolve()

            cmd = [
                sys.executable,
                str(PROJECT_ROOT / "generate_from_folder.py"),
                "--input", str(folder),
                "--output", str(generate_output),
                "--cluster-eps", str(params.get("cluster_eps", 0.08)),
                "--device", str(params.get("device", "auto")),
            ]
            if params.get("no_faces"):
                cmd.append("--no-faces")

            log_write(f"Comando: {' '.join(cmd)}")
            log_write("")

            try:
                result = subprocess.run(
                    cmd,
                    stdout=open(log_path, "a"),
                    stderr=subprocess.STDOUT,
                    text=True,
                    cwd=PROJECT_ROOT,
                    timeout=3600,  # 1 hora máx
                )
                if result.returncode != 0:
                    update_job(job_id, status="error", error=f"generate_from_folder.py falló (exit code {result.returncode})")
                    return
                images_dir = generate_output
                log_write("")
                log_write("✓ Generación completada")
            except subprocess.TimeoutExpired:
                update_job(job_id, status="error", error="generate_from_folder.py tardó más de 1 hora")
                return
            except Exception as e:
                update_job(job_id, status="error", error=f"Error ejecutando generate_from_folder.py: {e}")
                return

        # Step de main.py
        log_write("")
        log_write("Ejecutando main.py...")
        log_write("")
        update_job(job_id, status="running_main", stage="Asociando frases con imágenes")

        # Escribe la letra a un archivo temporal
        lyrics_txt = job_dir / "lyrics.txt"
        lyrics_txt.write_text(params["lyrics_text"], encoding="utf-8")

        # Prepara el comando main.py
        main_output = params.get("main_output")
        if not main_output:
            main_output = str(job_dir / "main_output")
        main_output = Path(main_output).expanduser().resolve()
        main_output.mkdir(parents=True, exist_ok=True)

        cmd = [
            sys.executable,
            str(PROJECT_ROOT / "main.py"),
            "--images", str(images_dir),
            "--lyrics", str(lyrics_txt),
            "--format", params.get("format", "instagram_4_5"),
            "--top-k", str(params.get("top_k", 5)),
            "--device", params.get("device", "auto"),
            "--output", str(main_output),
        ]
        if params.get("favorites_path"):
            cmd.extend(["--favorites", str(params["favorites_path"])])

        log_write(f"Comando: {' '.join(cmd)}")
        log_write("")

        try:
            result = subprocess.run(
                cmd,
                stdout=open(log_path, "a"),
                stderr=subprocess.STDOUT,
                text=True,
                cwd=PROJECT_ROOT,
                timeout=3600,
            )
            if result.returncode != 0:
                update_job(job_id, status="error", error=f"main.py falló (exit code {result.returncode})")
                return

            log_write("")
            log_write("✓ Pipeline completado con éxito")
            review_html = main_output / "review.html"
            if review_html.exists():
                review_url = f"/jobs/{job_id}/review/review.html"
                update_job(job_id, status="done", review_url=review_url, main_output=str(main_output))
            else:
                update_job(job_id, status="error", error="review.html no fue generado")

        except subprocess.TimeoutExpired:
            update_job(job_id, status="error", error="main.py tardó más de 1 hora")
        except Exception as e:
            update_job(job_id, status="error", error=f"Error ejecutando main.py: {e}")

    except Exception as e:
        update_job(job_id, status="error", error=f"Error interno: {e}")


# --------------------------------------------------------------------------
# Rutas Flask
# --------------------------------------------------------------------------


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/jobs", methods=["POST"])
def submit_job():
    """Recibe el formulario, valida, crea un job_id y lanza un hilo de fondo."""
    data = request.get_json() or {}

    # Validaciones
    folder = (data.get("folder") or "").strip()
    lyrics_text = (data.get("lyrics_text") or "").strip()
    favorites_path = (data.get("favorites_path") or "").strip()

    if not folder:
        return jsonify({"error": "Carpeta requerida"}), 400

    folder_path = Path(folder).expanduser().resolve()
    if not folder_path.exists():
        return jsonify({"error": f"Carpeta no existe: {folder}"}), 400
    if not folder_path.is_dir():
        return jsonify({"error": f"No es una carpeta: {folder}"}), 400

    if not lyrics_text:
        return jsonify({"error": "Letra requerida"}), 400

    if favorites_path:
        fav_path = Path(favorites_path).expanduser().resolve()
        if not fav_path.exists():
            return jsonify({"error": f"Archivo de favoritos no existe: {favorites_path}"}), 400

    # Crea el job
    job_id = str(uuid.uuid4())
    job_dir = JOBS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    with JOBS_LOCK:
        JOBS[job_id] = {
            "status": "pending",
            "stage": "Iniciando...",
            "log_path": str(job_dir / "log.txt"),
            "main_output": None,
            "review_url": None,
            "error": None,
        }

    # Lanza el hilo
    thread = threading.Thread(target=run_job, args=(job_id, data), daemon=True)
    thread.start()

    return jsonify({"job_id": job_id}), 202


@app.route("/api/jobs/<job_id>")
def get_status(job_id):
    """Retorna el estado actual del job (con cola del log)."""
    job = get_job(job_id)
    if not job:
        return jsonify({"error": "Job no encontrado"}), 404

    # Lee el log actual
    log_path = Path(job["log_path"])
    log_tail = read_log_tail(log_path, lines=100)

    return jsonify({
        "job_id": job_id,
        "status": job["status"],
        "stage": job["stage"],
        "log_tail": log_tail,
        "review_url": job["review_url"],
        "error": job["error"],
    })


@app.route("/api/browse")
def browse_folders():
    """Lista subcarpetas de un directorio, para el selector visual de carpetas."""
    raw_path = request.args.get("path", "").strip()
    current = Path(raw_path).expanduser().resolve() if raw_path else Path.home()

    if not current.exists() or not current.is_dir():
        return jsonify({"error": f"No es una carpeta válida: {current}"}), 400

    dirs = []
    try:
        entries = sorted(current.iterdir(), key=lambda p: p.name.lower())
    except PermissionError:
        return jsonify({"error": f"Sin permiso para leer: {current}"}), 403

    for entry in entries:
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        try:
            has_metadata = (entry / "metadata.json").exists()
        except PermissionError:
            has_metadata = False
        dirs.append({"name": entry.name, "path": str(entry), "has_metadata": has_metadata})

    parent = str(current.parent) if current.parent != current else None

    return jsonify({
        "current": str(current),
        "parent": parent,
        "has_metadata": (current / "metadata.json").exists(),
        "dirs": dirs,
    })


@app.route("/jobs/<job_id>/review/<path:subpath>")
def serve_review(job_id, subpath):
    """Sirve archivos desde la carpeta de salida del job (con guard contra path traversal)."""
    job = get_job(job_id)
    if not job or not job["main_output"]:
        return "Job no encontrado", 404

    base = Path(job["main_output"]).resolve()
    target = (base / subpath).resolve()

    # Guard contra path traversal
    try:
        target.relative_to(base)
    except ValueError:
        return "Acceso denegado", 403

    return send_from_directory(base, subpath)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"Servidor iniciado en http://localhost:5000")
    print(f"Abre esa URL en tu navegador.")
    app.run(debug=False, host="127.0.0.1", port=5000)
