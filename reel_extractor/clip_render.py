"""Renderiza cada ventana elegida como un clip vertical (recorte centrado +
escalado), y opcionalmente quema subtitulos sobre el clip final con ffmpeg.

Los nombres/medidas de formato coinciden con lyrics_social/composer.py::FORMATS
para consistencia, aunque aqui se aplican a video (ffmpeg) y no a fotos (PIL).
"""
from pathlib import Path

from ._ffmpeg_utils import run

FORMATS = {
    "story": (1080, 1920),
    "square": (1080, 1080),
}


def probe_video_size(input_path):
    """Retorna (width, height) del video de entrada via ffprobe."""
    out = run([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=p=0", str(input_path),
    ])
    w_str, h_str = out.strip().split(",")
    return int(w_str), int(h_str)


def _cover_crop_filter(src_w, src_h, target_w, target_h):
    """Calcula el filtro ffmpeg crop=W:H (centrado) que recorta src_w x src_h
    al aspect ratio de target_w x target_h sin deformar, misma logica que
    _cover_crop en composer.py pero expresada como filtro ffmpeg."""
    target_ratio = target_w / target_h
    src_ratio = src_w / src_h

    if src_ratio > target_ratio:
        crop_h = src_h
        crop_w = round(crop_h * target_ratio)
    else:
        crop_w = src_w
        crop_h = round(crop_w / target_ratio)

    x = (src_w - crop_w) // 2
    y = (src_h - crop_h) // 2
    return f"crop={crop_w}:{crop_h}:{x}:{y}"


def render_vertical_clip(input_path, start, end, out_path, format_name="story"):
    """Recorta [start, end] del video, lo recorta al centro segun format_name
    y escala al tamano final. Copia el audio sin re-codificar cuando es
    posible (se recodifica igual por el -ss/-t, asi que se usa aac simple)."""
    target_w, target_h = FORMATS[format_name]
    src_w, src_h = probe_video_size(input_path)
    crop_filter = _cover_crop_filter(src_w, src_h, target_w, target_h)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    run([
        "ffmpeg", "-y",
        "-ss", f"{start:.3f}", "-i", str(input_path), "-t", f"{end - start:.3f}",
        "-vf", f"{crop_filter},scale={target_w}:{target_h}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "128k",
        str(out_path),
    ])
    return out_path


def burn_subtitles(clip_path, srt_path, out_path):
    """Quema subtitulos sobre un clip ya renderizado usando el filtro
    ffmpeg 'subtitles' (requiere libass, comunmente incluido en ffmpeg)."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    srt_escaped = str(srt_path).replace(":", r"\:")
    run([
        "ffmpeg", "-y", "-i", str(clip_path),
        "-vf", f"subtitles={srt_escaped}:force_style='FontSize=24,Alignment=2,MarginV=80'",
        "-c:a", "copy",
        str(out_path),
    ])
    return out_path
