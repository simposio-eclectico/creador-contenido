"""Wrapper minimo de subprocess para invocar ffmpeg/ffprobe (mismo patron que
video_processor/generate.py; se duplica aqui en vez de importar entre paquetes
hermanos para evitar acoplar el sys.path de ambos modulos)."""
import subprocess


def run(cmd):
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
