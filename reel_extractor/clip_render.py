"""Renderiza cada ventana elegida como un clip vertical (recorte centrado +
escalado), y opcionalmente quema subtitulos sobre el clip final con ffmpeg.

Los nombres/medidas de formato coinciden con lyrics_social/composer.py::FORMATS
para consistencia, aunque aqui se aplican a video (ffmpeg) y no a fotos (PIL).
"""
from pathlib import Path

from ._ffmpeg_utils import run
from .fonts import resolve_font_path

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


def burn_subtitles(clip_path, segments, out_path, font_name=None):
    """Quema subtitulos sobre un clip ya renderizado encadenando un filtro
    'drawtext' por segmento (con enable=between(t,start,end)). Se prefiere
    drawtext sobre el filtro 'subtitles' porque este ultimo requiere libass,
    que no viene habilitado en todas las builds de ffmpeg por defecto
    (p.ej. Homebrew); ver _ffmpeg_utils.py::resolve_ffmpeg_binary para como
    se detecta un binario con soporte completo si esta instalado.

    segments: lista de dicts {"start", "end", "text"} en tiempo relativo
    al clip (0 = inicio del clip).
    font_name: clave de fonts.py::FONT_CATALOG (default 'im_fell').
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not segments:
        run(["ffmpeg", "-y", "-i", str(clip_path), "-c", "copy", str(out_path)])
        return out_path

    font_path = resolve_font_path(font_name)
    fontfile_clause = f"fontfile='{_escape_drawtext(str(font_path))}':" if font_path else ""

    filters = []
    for seg in segments:
        text = _escape_drawtext(seg["text"])
        filters.append(
            "drawtext="
            f"{fontfile_clause}"
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


def apply_fade(clip_path, out_path, clip_duration, fade_duration=3.0, fade_target="black", fade_image_path=None, format_name="story"):
    """Aplica un fadeout de audio y video en los ultimos fade_duration
    segundos del clip. fade_target: "black" (fade a negro, filtro 'fade'
    nativo) o "image" (disuelve hacia una imagen fija superpuesta con
    'overlay', requiere fade_image_path).
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fade_start = max(0.0, clip_duration - fade_duration)
    afade = f"afade=t=out:st={fade_start:.3f}:d={fade_duration:.3f}"

    if fade_target == "image" and fade_image_path:
        target_w, target_h = FORMATS[format_name]
        vf_complex = (
            f"[1:v]scale={target_w}:{target_h}:force_original_aspect_ratio=increase,"
            f"crop={target_w}:{target_h},format=yuva420p,"
            f"fade=t=in:st=0:d={fade_duration:.3f}:alpha=1[imgfade];"
            f"[0:v][imgfade]overlay=enable='gte(t,{fade_start:.3f})'[vout]"
        )
        run([
            "ffmpeg", "-y",
            "-i", str(clip_path),
            "-loop", "1", "-t", f"{fade_duration:.3f}", "-i", str(fade_image_path),
            "-filter_complex", vf_complex,
            "-map", "[vout]", "-map", "0:a",
            "-af", afade,
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "aac", "-b:a", "128k",
            str(out_path),
        ])
    else:
        vf = f"fade=t=out:st={fade_start:.3f}:d={fade_duration:.3f}:color=black"
        run([
            "ffmpeg", "-y", "-i", str(clip_path),
            "-vf", vf,
            "-af", afade,
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "aac", "-b:a", "128k",
            str(out_path),
        ])
    return out_path
