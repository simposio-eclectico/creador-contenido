#!/usr/bin/env python3
"""
burn_subs.py - Quema subtitulos (posiblemente editados por el usuario) sobre
un clip ya renderizado por extract.py.

Se invoca como paso separado despues de que extract.py corrio con
--skip-burn: permite editar el texto transcrito por Whisper antes de
quemarlo, sin tener que repetir la deteccion de highlights ni la
transcripcion completa (ambos pasos caros).

Uso:
  python3 burn_subs.py --clip reel_output/clips/01.mp4 \
      --segments segments.json --output reel_output/clips/01_subtitled.mp4 \
      --font im_fell

segments.json: lista de objetos {"start": float, "end": float, "text": str},
en tiempo relativo al clip (0 = inicio del clip). Mismo formato que
reel["segments"] en metadata.json.
"""
import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from reel_extractor.clip_render import burn_subtitles
from reel_extractor.fonts import FONT_CATALOG
from reel_extractor.transcribe import write_srt


def main():
    ap = argparse.ArgumentParser(description="Quema subtitulos (editables) sobre un clip ya renderizado.")
    ap.add_argument("--clip", required=True, help="Ruta al clip de video ya renderizado")
    ap.add_argument("--segments", required=True, help="Ruta a JSON con lista de {start,end,text}")
    ap.add_argument("--output", required=True, help="Ruta de salida para el clip con subtitulos quemados")
    ap.add_argument("--srt-output", help="Si se pasa, ademas re-escribe el .srt con el texto (posiblemente editado)")
    ap.add_argument("--font", default="im_fell", choices=sorted(FONT_CATALOG))
    ap.add_argument("--font-color", default="white", help="Color del texto (nombre o hex, default 'white')")
    ap.add_argument("--font-opacity", type=float, default=1.0, help="Transparencia del texto 0-1 (default 1.0)")
    ap.add_argument("--background-enabled", default="true", choices=["true", "false"], help="Dibuja fondo detras del texto")
    ap.add_argument("--background-color", default="black", help="Color del fondo (default 'black')")
    ap.add_argument("--background-opacity", type=float, default=0.55, help="Transparencia del fondo 0-1 (default 0.55)")
    ap.add_argument("--outline-enabled", default="false", choices=["true", "false"], help="Dibuja borde/contorno en el texto")
    ap.add_argument("--outline-color", default="black", help="Color del borde (default 'black')")
    ap.add_argument("--outline-width", type=int, default=2, help="Grosor del borde en px (default 2)")
    args = ap.parse_args()

    clip_path = Path(args.clip).resolve()
    if not clip_path.exists():
        sys.exit(f"No existe el clip: {clip_path}")

    segments = json.loads(Path(args.segments).read_text(encoding="utf-8"))

    if args.srt_output:
        write_srt(segments, args.srt_output)

    burn_subtitles(
        clip_path, segments, args.output, font_name=args.font,
        font_color=args.font_color, font_opacity=args.font_opacity,
        background_enabled=args.background_enabled == "true",
        background_color=args.background_color, background_opacity=args.background_opacity,
        outline_enabled=args.outline_enabled == "true",
        outline_color=args.outline_color, outline_width=args.outline_width,
    )
    print(f"Listo: {args.output}")


if __name__ == "__main__":
    main()
