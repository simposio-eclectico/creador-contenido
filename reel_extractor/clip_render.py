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
    """Retorna (width, height) del video de entrada via ffprobe.

    Usa -of json en vez de csv: algunos videos agregan columnas extra al
    csv (p.ej. side_data_list por rotacion), rompiendo un split(",") fijo
    en 2 valores. JSON evita ese problema por completo.
    """
    import json as _json

    out = run([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "json", str(input_path),
    ])
    stream = _json.loads(out)["streams"][0]
    return int(stream["width"]), int(stream["height"])


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


def _escape_drawtext(text):
    """Escapa caracteres especiales del filtro drawtext de ffmpeg."""
    return (
        text.replace("\\", r"\\\\")
        .replace(":", r"\:")
        .replace("'", r"\'")
        .replace("%", r"\%")
    )


def burn_subtitles(clip_path, segments, out_path):
    """Quema subtitulos sobre un clip ya renderizado encadenando un filtro
    'drawtext' por segmento (con enable=between(t,start,end)). Se prefiere
    drawtext sobre el filtro 'subtitles' porque este ultimo requiere libass,
    que no viene habilitado en todas las builds de ffmpeg (p.ej. algunas
    instalaciones via Homebrew), mientras que drawtext siempre esta disponible.

    segments: lista de dicts {"start", "end", "text"} en tiempo relativo
    al clip (0 = inicio del clip).
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not segments:
        run(["ffmpeg", "-y", "-i", str(clip_path), "-c", "copy", str(out_path)])
        return out_path

    filters = []
    for seg in segments:
        text = _escape_drawtext(seg["text"])
        filters.append(
            "drawtext="
            f"text='{text}':"
            "fontsize=42:fontcolor=white:box=1:boxcolor=black@0.55:boxborderw=12:"
            "x=(w-text_w)/2:y=h-220:"
            f"enable='between(t,{seg['start']:.3f},{seg['end']:.3f})'"
        )
    vf = ",".join(filters)

    run([
        "ffmpeg", "-y", "-i", str(clip_path),
        "-vf", vf,
        "-c:a", "copy",
        str(out_path),
    ])
    return out_path
