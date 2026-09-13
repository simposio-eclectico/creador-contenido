"""Wrapper minimo de subprocess para invocar ffmpeg/ffprobe (mismo patron que
video_processor/generate.py; se duplica aqui en vez de importar entre paquetes
hermanos para evitar acoplar el sys.path de ambos modulos).

Resuelve automaticamente un binario de ffmpeg con soporte para 'drawtext' y
'subtitles' (requieren libfreetype/libass) si esta disponible, ya que builds
por defecto de algunos gestores de paquetes (p.ej. Homebrew) no las incluyen.
Ver resolve_ffmpeg_binary().
"""
import os
import subprocess
from pathlib import Path

# Candidatos conocidos de instalaciones "full" que sí incluyen libfreetype/libass
# (p.ej. `brew install ffmpeg-full`, que es keg-only y no reemplaza al ffmpeg
# por defecto). Se puede forzar un binario propio con las variables de entorno
# REEL_FFMPEG_BIN / REEL_FFPROBE_BIN.
_FFMPEG_FULL_CANDIDATES = [
    "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg",
    "/usr/local/opt/ffmpeg-full/bin/ffmpeg",
]
_FFPROBE_FULL_CANDIDATES = [
    "/opt/homebrew/opt/ffmpeg-full/bin/ffprobe",
    "/usr/local/opt/ffmpeg-full/bin/ffprobe",
]


def _resolve_binary(env_var, candidates, fallback_name):
    override = os.environ.get(env_var)
    if override and Path(override).exists():
        return override
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    return fallback_name  # cae al binario del PATH


FFMPEG_BIN = _resolve_binary("REEL_FFMPEG_BIN", _FFMPEG_FULL_CANDIDATES, "ffmpeg")
FFPROBE_BIN = _resolve_binary("REEL_FFPROBE_BIN", _FFPROBE_FULL_CANDIDATES, "ffprobe")


def run(cmd):
    if cmd and cmd[0] == "ffmpeg":
        cmd = [FFMPEG_BIN, *cmd[1:]]
    elif cmd and cmd[0] == "ffprobe":
        cmd = [FFPROBE_BIN, *cmd[1:]]

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Comando fallido: {' '.join(cmd)}\n{result.stderr}")
    return result.stdout


def probe_duration(input_path):
    out = run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(input_path),
    ])
    return float(out.strip())
