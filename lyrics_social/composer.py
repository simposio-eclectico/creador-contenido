"""Compositor: recorta al formato pedido y prepara el fondo (foto + degrade)
evitando la cara, usando face_position de metadata.json (ver selector-fotogramas
README).

El texto en si NO se hornea aca salvo para las miniaturas de candidatas
(`compose`, con un estilo por defecto). La composicion final interactiva
(tipografia/color/efecto por linea, elegibles en review.html) se dibuja en
el navegador con <canvas> sobre el fondo que produce `compose_background`,
para poder cambiar el estilo al instante sin volver a correr Python.

Deliberadamente separado del matching (ver matching.py): a estas funciones
no les importa por que se eligio una imagen para una frase, solo como
maquetarlas.
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

FORMATS = {
    "instagram_4_5": (1080, 1350),
    "square": (1080, 1080),
    "story": (1080, 1920),
}

# Fraccion de alto que ocupa el degrade/zona de texto. Debe coincidir con
# BAND_FRAC en review.py (JS) para que la vista previa del navegador
# coincida con lo que produce compose() al hornear un export.
BAND_FRAC = 0.32

FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def _load_font(size):
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _cover_crop(img, target_w, target_h, face_cy):
    """Rellena todo el lienzo (sin bandas vacias): escala para cubrir y
    recorta el sobrante, sesgando el recorte vertical hacia la cara si la hay."""
    target_ratio = target_w / target_h
    w, h = img.size
    ratio = w / h

    if ratio > target_ratio:
        # imagen mas ancha que el objetivo: recortar los costados, centrado
        scale = target_h / h
        resized = img.resize((round(w * scale), target_h))
        w2, h2 = resized.size
        x0 = (w2 - target_w) // 2
        return resized.crop((x0, 0, x0 + target_w, target_h))

    # imagen mas alta que el objetivo: recortar arriba/abajo, sesgado hacia la cara
    scale = target_w / w
    resized = img.resize((target_w, round(h * scale)))
    w2, h2 = resized.size
    if face_cy is not None:
        center_y = face_cy * h2
    else:
        center_y = h2 / 2
    y0 = int(round(center_y - target_h / 2))
    y0 = max(0, min(y0, h2 - target_h))
    return resized.crop((0, y0, target_w, y0 + target_h))


def _vertical_gradient(width, height, y0, y1, alpha0, alpha1):
    """Capa RGBA negra con alpha en degrade entre y0 y y1 (resto, plano)."""
    alpha = np.zeros(height, dtype=np.uint8)
    if y0 > 0:
        alpha[:y0] = alpha0
    if y1 > y0:
        alpha[y0:y1] = np.linspace(alpha0, alpha1, y1 - y0)
    if y1 < height:
        alpha[y1:] = alpha1
    rgba = np.zeros((height, width, 4), dtype=np.uint8)
    rgba[..., 3] = np.tile(alpha.reshape(-1, 1), (1, width))
    return Image.fromarray(rgba, mode="RGBA")


def _wrap_to_width(draw, text, font, max_width):
    words = text.split()
    lines, current = [], ""
    for word in words:
        trial = f"{current} {word}".strip()
        if current and draw.textlength(trial, font=font) > max_width:
            lines.append(current)
            current = word
        else:
            current = trial
    if current:
        lines.append(current)
    return "\n".join(lines)


def text_anchor(frame):
    """'top' o 'bottom': donde va la zona de texto/degrade para esta imagen."""
    face_position = frame.get("face_position")
    face_in_bottom = face_position is not None and face_position[1] > 0.5
    return "top" if face_in_bottom else "bottom"


def compose_background(image_path, frame, format_name, output_path):
    """Recorte + degrade, sin texto. Es el fondo que usa el <canvas> del
    review.html para dibujar el texto en vivo con el estilo que se elija."""
    target_w, target_h = FORMATS[format_name]
    img = Image.open(image_path).convert("RGBA")

    face_position = frame.get("face_position")
    face_cy = face_position[1] if face_position else None
    canvas = _cover_crop(img, target_w, target_h, face_cy)

    band_h = round(target_h * BAND_FRAC)
    if text_anchor(frame) == "top":
        scrim = _vertical_gradient(target_w, target_h, y0=0, y1=band_h, alpha0=190, alpha1=0)
    else:
        scrim = _vertical_gradient(target_w, target_h, y0=target_h - band_h, y1=target_h, alpha0=0, alpha1=190)

    canvas = Image.alpha_composite(canvas, scrim)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(output_path, quality=92)


def compose(image_path, text, frame, format_name, output_path):
    """Fondo + texto con el estilo por defecto (contorno negro, blanco).
    Usado para las miniaturas de candidatas y para exportar sin navegador."""
    target_w, target_h = FORMATS[format_name]
    img = Image.open(image_path).convert("RGBA")

    face_position = frame.get("face_position")
    face_cy = face_position[1] if face_position else None
    canvas = _cover_crop(img, target_w, target_h, face_cy)

    draw = ImageDraw.Draw(canvas)
    font = _load_font(round(target_w * 0.062))
    wrapped = _wrap_to_width(draw, text, font, round(target_w * 0.82))
    bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=10, align="center")
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]

    padding = round(font.size * 1.1)
    band_h = min(target_h, max(text_h + padding * 2, round(target_h * BAND_FRAC)))

    anchor = text_anchor(frame)
    if anchor == "top":
        scrim = _vertical_gradient(target_w, target_h, y0=0, y1=band_h, alpha0=190, alpha1=0)
        text_y = padding - bbox[1]
    else:
        scrim = _vertical_gradient(target_w, target_h, y0=target_h - band_h, y1=target_h, alpha0=0, alpha1=190)
        text_y = target_h - band_h + padding - bbox[1]

    canvas = Image.alpha_composite(canvas, scrim)
    draw = ImageDraw.Draw(canvas)
    tx = (target_w - text_w) / 2 - bbox[0]
    draw.multiline_text(
        (tx, text_y), wrapped, font=font, fill=(255, 255, 255, 255),
        align="center", spacing=10,
        stroke_width=max(2, font.size // 16), stroke_fill=(0, 0, 0, 210),
    )

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(output_path, quality=92)
