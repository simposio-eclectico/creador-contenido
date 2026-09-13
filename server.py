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
from werkzeug.utils import secure_filename

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

        selection_mode = params.get("selection_mode", "auto")
        if selection_mode not in ("auto", "manual"):
            selection_mode = "auto"

        cmd = [
            sys.executable,
            str(PROJECT_ROOT / "main.py"),
            "--images", str(images_dir),
            "--lyrics", str(lyrics_txt),
            "--format", params.get("format", "instagram_4_5"),
            "--selection-mode", selection_mode,
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


def run_video_job(job_id: str, video_path: str):
    """Ejecuta video_processor/generate.py en un hilo de fondo."""
    job = get_job(job_id)
    job_dir = JOBS_DIR / job_id
    output_dir = job_dir / "video_output"
    log_path = job_dir / "log.txt"

    def log_write(msg: str, end="\n"):
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(msg + end)

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        update_job(job_id, status="processing", stage="Procesando video...")

        cmd = [
            sys.executable,
            str(PROJECT_ROOT / "video_processor" / "generate.py"),
            "--input", str(video_path),
            "--output", str(output_dir),
        ]

        log_write(f"Procesando video: {Path(video_path).name}")
        log_write(f"Comando: {' '.join(cmd)}")
        log_write("")

        result = subprocess.run(
            cmd,
            stdout=open(log_path, "a"),
            stderr=subprocess.STDOUT,
            text=True,
            cwd=PROJECT_ROOT,
            timeout=3600,
        )

        if result.returncode != 0:
            update_job(
                job_id,
                status="error",
                error=f"Video processing failed (exit {result.returncode})",
            )
            return

        log_write("")
        log_write("✓ Video processing complete")
        update_job(job_id, status="done", video_output=str(output_dir))

    except subprocess.TimeoutExpired:
        update_job(job_id, status="error", error="Video processing timeout")
    except Exception as e:
        update_job(job_id, status="error", error=f"Error: {e}")


def run_reel_job(job_id: str, video_path: str, params: dict):
    """Ejecuta reel_extractor/extract.py en un hilo de fondo."""
    job_dir = JOBS_DIR / job_id
    output_dir = job_dir / "reel_output"
    log_path = job_dir / "log.txt"

    def log_write(msg: str, end="\n"):
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(msg + end)

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        update_job(job_id, status="processing", stage="Detectando highlights...")

        cmd = [
            sys.executable,
            str(PROJECT_ROOT / "reel_extractor" / "extract.py"),
            "--input", str(video_path),
            "--output", str(output_dir),
            "--duration", str(params.get("duration", 30)),
            "--count", str(params.get("count", 3)),
            "--audio-weight", str(params.get("audio_weight", 0.5)),
            "--format", params.get("format", "story"),
            "--whisper-model", params.get("whisper_model", "base"),
            "--subtitle-font", params.get("subtitle_font", "im_fell"),
            "--language", params.get("language", "es"),
        ]
        if params.get("subtitles"):
            cmd.append("--subtitles")
            # No quema todavia: el usuario revisa/edita el texto transcrito
            # en el frontend antes de confirmar (ver /api/reel-jobs/<id>/confirm-subtitles)
            cmd.append("--skip-burn")

        fade_out = float(params.get("fade_out", 0) or 0)
        if fade_out > 0:
            cmd.extend(["--fade-out", str(fade_out), "--fade-target", params.get("fade_target", "black")])
            if params.get("fade_target") == "image" and params.get("fade_image_path"):
                cmd.extend(["--fade-image", str(params["fade_image_path"])])

        log_write(f"Procesando video para reels: {Path(video_path).name}")
        log_write(f"Comando: {' '.join(cmd)}")
        log_write("")

        result = subprocess.run(
            cmd,
            stdout=open(log_path, "a"),
            stderr=subprocess.STDOUT,
            text=True,
            cwd=PROJECT_ROOT,
            timeout=3600,
        )

        if result.returncode != 0:
            update_job(
                job_id,
                status="error",
                error=f"Reel extraction failed (exit {result.returncode})",
            )
            return

        metadata_path = output_dir / "metadata.json"
        if not metadata_path.exists():
            update_job(job_id, status="error", error="metadata.json no fue generado")
            return

        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

        log_write("")
        if metadata.get("subtitles_pending_review"):
            log_write("✓ Reels listos, subtitulos pendientes de revision")
            update_job(
                job_id, status="awaiting_review", stage="Revisa los subtitulos antes de confirmar",
                reel_output=str(output_dir), reels=metadata["reels"],
                subtitle_font=metadata.get("subtitle_font", "im_fell"),
            )
        else:
            log_write("✓ Reel extraction complete")
            update_job(job_id, status="done", reel_output=str(output_dir), reels=metadata["reels"])

    except subprocess.TimeoutExpired:
        update_job(job_id, status="error", error="Reel extraction timeout")
    except Exception as e:
        update_job(job_id, status="error", error=f"Error: {e}")


def run_burn_subtitles_job(job_id: str, reels_edits: list):
    """Quema subtitulos (con texto posiblemente editado) para cada reel del
    job, invocando burn_subs.py por separado (no repite deteccion ni
    transcripcion, que ya corrieron en run_reel_job)."""
    job = get_job(job_id)
    output_dir = Path(job["reel_output"])
    log_path = Path(job["log_path"])

    def log_write(msg: str, end="\n"):
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(msg + end)

    try:
        update_job(job_id, status="processing", stage="Quemando subtitulos editados...")
        reels_by_id = {r["id"]: r for r in job["reels"]}
        font_name = job.get("subtitle_font", "im_fell")

        for edit in reels_edits:
            reel_id = edit["id"]
            reel = reels_by_id.get(reel_id)
            if not reel or not reel.get("clip"):
                continue

            segments = edit.get("segments") or []
            segments_json_path = output_dir / f"_edit_segments_{reel_id:02d}.json"
            segments_json_path.write_text(json.dumps(segments, ensure_ascii=False), encoding="utf-8")

            clip_path = output_dir / reel["clip"]
            burned_name = f"{reel_id:02d}_subtitled.mp4"
            burned_path = clip_path.parent / burned_name
            srt_path = output_dir / reel["srt"] if reel.get("srt") else None

            cmd = [
                sys.executable,
                str(PROJECT_ROOT / "reel_extractor" / "burn_subs.py"),
                "--clip", str(clip_path),
                "--segments", str(segments_json_path),
                "--output", str(burned_path),
                "--font", font_name,
            ]
            if srt_path:
                cmd.extend(["--srt-output", str(srt_path)])

            log_write(f"Quemando subtitulos editados en reel #{reel_id}...")
            log_write(f"Comando: {' '.join(cmd)}")

            result = subprocess.run(
                cmd, stdout=open(log_path, "a"), stderr=subprocess.STDOUT,
                text=True, cwd=PROJECT_ROOT, timeout=600,
            )
            segments_json_path.unlink(missing_ok=True)

            if result.returncode != 0:
                log_write(f"Aviso: fallo al quemar subtitulos en reel #{reel_id} (exit {result.returncode})")
                continue

            reel["clip_with_subtitles"] = f"clips/{burned_name}"
            reel["segments"] = segments

        log_write("")
        log_write("✓ Subtitulos aplicados")
        update_job(job_id, status="done", reels=list(reels_by_id.values()))

    except subprocess.TimeoutExpired:
        update_job(job_id, status="error", error="Timeout al quemar subtitulos")
    except Exception as e:
        update_job(job_id, status="error", error=f"Error: {e}")


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


@app.route("/api/upload-video", methods=["POST"])
def upload_video():
    """Recibe archivo de video y inicia procesamiento."""
    if "video" not in request.files:
        return jsonify({"error": "Sin archivo de video"}), 400

    file = request.files["video"]
    if file.filename == "":
        return jsonify({"error": "Archivo vacío"}), 400

    job_id = str(uuid.uuid4())
    job_dir = JOBS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    filename = secure_filename(file.filename)
    input_path = job_dir / filename
    file.save(input_path)

    with JOBS_LOCK:
        JOBS[job_id] = {
            "type": "video",
            "status": "pending",
            "stage": "Iniciando...",
            "log_path": str(job_dir / "log.txt"),
            "video_output": None,
            "error": None,
        }

    thread = threading.Thread(
        target=run_video_job, args=(job_id, str(input_path)), daemon=True
    )
    thread.start()

    return jsonify({"job_id": job_id}), 202


@app.route("/api/video-jobs/<job_id>")
def get_video_status(job_id):
    """Retorna estado del job de procesamiento de video."""
    job = get_job(job_id)
    if not job or job.get("type") != "video":
        return jsonify({"error": "Job no encontrado"}), 404

    log_path = Path(job["log_path"])
    log_tail = read_log_tail(log_path, lines=100)

    return jsonify({
        "job_id": job_id,
        "status": job["status"],
        "stage": job["stage"],
        "log_tail": log_tail,
        "video_output": job.get("video_output"),
        "error": job.get("error"),
    })


@app.route("/api/upload-reel-video", methods=["POST"])
def upload_reel_video():
    """Recibe archivo de video e inicia extraccion de reels."""
    if "video" not in request.files:
        return jsonify({"error": "Sin archivo de video"}), 400

    file = request.files["video"]
    if file.filename == "":
        return jsonify({"error": "Archivo vacío"}), 400

    duration = request.form.get("duration", "30")
    count = request.form.get("count", "3")
    audio_weight = request.form.get("audio_weight", "0.5")
    format_name = request.form.get("format", "story")
    subtitles = request.form.get("subtitles") in ("1", "true", "on")
    whisper_model = request.form.get("whisper_model", "base")
    subtitle_font = request.form.get("subtitle_font", "im_fell")
    language = request.form.get("language", "es")
    fade_out = request.form.get("fade_out", "0")
    fade_target = request.form.get("fade_target", "black")

    job_id = str(uuid.uuid4())
    job_dir = JOBS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    filename = secure_filename(file.filename)
    input_path = job_dir / filename
    file.save(input_path)

    fade_image_path = None
    fade_image_file = request.files.get("fade_image")
    if fade_image_file and fade_image_file.filename:
        fade_image_name = secure_filename(fade_image_file.filename)
        fade_image_path = job_dir / f"fade_{fade_image_name}"
        fade_image_file.save(fade_image_path)

    with JOBS_LOCK:
        JOBS[job_id] = {
            "type": "reel",
            "status": "pending",
            "stage": "Iniciando...",
            "log_path": str(job_dir / "log.txt"),
            "reel_output": None,
            "reels": None,
            "error": None,
        }

    params = {
        "duration": duration,
        "count": count,
        "audio_weight": audio_weight,
        "format": format_name,
        "subtitles": subtitles,
        "whisper_model": whisper_model,
        "subtitle_font": subtitle_font,
        "language": language,
        "fade_out": fade_out,
        "fade_target": fade_target,
        "fade_image_path": str(fade_image_path) if fade_image_path else None,
    }
    thread = threading.Thread(
        target=run_reel_job, args=(job_id, str(input_path), params), daemon=True
    )
    thread.start()

    return jsonify({"job_id": job_id}), 202


@app.route("/api/reel-jobs/<job_id>")
def get_reel_status(job_id):
    """Retorna estado del job de extraccion de reels."""
    job = get_job(job_id)
    if not job or job.get("type") != "reel":
        return jsonify({"error": "Job no encontrado"}), 404

    log_path = Path(job["log_path"])
    log_tail = read_log_tail(log_path, lines=100)

    reels = job.get("reels")
    reels_out = None
    if reels:
        reels_out = [
            {
                **r,
                "clip_url": f"/jobs/{job_id}/reel-output/{r['clip']}",
                "srt_url": f"/jobs/{job_id}/reel-output/{r['srt']}" if r.get("srt") else None,
                "burned_clip_url": (
                    f"/jobs/{job_id}/reel-output/{r['clip_with_subtitles']}"
                    if r.get("clip_with_subtitles") else None
                ),
            }
            for r in reels
        ]

    return jsonify({
        "job_id": job_id,
        "status": job["status"],
        "stage": job["stage"],
        "log_tail": log_tail,
        "reels": reels_out,
        "error": job.get("error"),
    })


@app.route("/api/reel-jobs/<job_id>/confirm-subtitles", methods=["POST"])
def confirm_reel_subtitles(job_id):
    """Recibe los segmentos de subtitulos (posiblemente editados por el
    usuario) y dispara la quema sobre los clips ya generados."""
    job = get_job(job_id)
    if not job or job.get("type") != "reel":
        return jsonify({"error": "Job no encontrado"}), 404
    if job["status"] != "awaiting_review":
        return jsonify({"error": f"El job no esta esperando revision (status={job['status']})"}), 400

    data = request.get_json() or {}
    reels_edits = data.get("reels")
    if not isinstance(reels_edits, list) or not reels_edits:
        return jsonify({"error": "Se requiere 'reels': [{id, segments}, ...]"}), 400

    thread = threading.Thread(target=run_burn_subtitles_job, args=(job_id, reels_edits), daemon=True)
    thread.start()

    return jsonify({"job_id": job_id}), 202


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


@app.route("/jobs/<job_id>/video-output/<path:subpath>")
def serve_video_output(job_id, subpath):
    """Sirve archivos desde salida de procesamiento video."""
    job = get_job(job_id)
    if not job or not job.get("video_output"):
        return "Job no encontrado", 404

    base = Path(job["video_output"]).resolve()
    target = (base / subpath).resolve()

    try:
        target.relative_to(base)
    except ValueError:
        return "Acceso denegado", 403

    return send_from_directory(base, subpath)


@app.route("/jobs/<job_id>/reel-output/<path:subpath>")
def serve_reel_output(job_id, subpath):
    """Sirve archivos desde salida de extraccion de reels (clips, .srt)."""
    job = get_job(job_id)
    if not job or not job.get("reel_output"):
        return "Job no encontrado", 404

    base = Path(job["reel_output"]).resolve()
    target = (base / subpath).resolve()

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
