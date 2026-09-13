"""Catalogo de tipografias disponibles para quemar subtitulos con drawtext.

IM Fell DW Pica viene vendorizada en reel_extractor/fonts/ (SIL Open Font
License, ver fonts/OFL.txt) porque es la misma familia que usa
lyrics_social/review.py para el texto de las composiciones, y drawtext
necesita un archivo de fuente real (no un nombre generico como en CSS).
Las demas opciones son fuentes de sistema comunes (mismo patron que
composer.py::FONT_CANDIDATES), con IM Fell como default.
"""
from pathlib import Path

FONTS_DIR = Path(__file__).resolve().parent / "fonts"

# nombre publico -> lista de rutas candidatas (la primera que exista se usa)
FONT_CATALOG = {
    "im_fell": [
        FONTS_DIR / "IMFellDWPica-Regular.ttf",
    ],
    "arial": [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ],
    "georgia": [
        "/System/Library/Fonts/Supplemental/Georgia.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    ],
    "courier": [
        "/System/Library/Fonts/Supplemental/Courier New.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ],
    "impact": [
        "/System/Library/Fonts/Supplemental/Impact.ttf",
    ],
    "helvetica": [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ],
}

DEFAULT_FONT = "im_fell"


def resolve_font_path(font_name=None):
    """Retorna la ruta al archivo de fuente para font_name (default 'im_fell').
    Si ninguna ruta candidata existe, retorna None (drawtext usa la fuente
    por defecto del sistema en ese caso)."""
    candidates = FONT_CATALOG.get(font_name or DEFAULT_FONT, FONT_CATALOG[DEFAULT_FONT])
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return path
    return None
