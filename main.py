#!/usr/bin/env python3
"""
main.py - Asocia frases de una letra con imagenes y compone piezas para redes.

Pipeline:
  1. Lee la letra (un archivo de texto, una frase por linea).
  2. Lee metadata.json de una carpeta generada por selector-fotogramas
     (necesita el campo "embedding" por fotograma).
  3. Elige las candidatas por frase segun --selection-mode:
     - "auto" (default): calcula embeddings de texto (OpenCLIP) y rankea,
       por frase, las top-k imagenes mas afines por similitud coseno (ver
       lyrics_social/matching.py para el punto de extension hacia relaciones
       asociativa/contrapunto).
     - "manual": todas las fotos quedan disponibles como candidatas en todas
       las frases, sin rankear, para que el usuario las compare a mano en
       review.html.
  4. Compone las candidatas de cada frase en el formato pedido, evitando
     tapar caras detectadas (lyrics_social/composer.py), para que review.html
     pueda mostrar el cambio al instante al elegir otra.
  5. Escribe associations.json (todas las candidatas) y review.html
     (vista interactiva: click en una candidata para previsualizarla).

Uso:
  python3 main.py --images ./mi-video-review --lyrics letra.txt \
      --format instagram_4_5
  # sin --output, escribe en ./mi-video-review/creator/

  # solo considerar los fotogramas marcados como favoritos en el visor:
  python3 main.py --images ./mi-video-review --lyrics letra.txt \
      --favorites ./mi-video-review-respaldo.json

  # modo manual: ver todas las fotos en todas las frases
  python3 main.py --images ./mi-video-review --lyrics letra.txt \
      --selection-mode manual
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

from lyrics_social.composer import FORMATS, compose, compose_background, text_anchor
from lyrics_social.images import load_image_library, frame_full_path
from lyrics_social.lyrics import load_lines
from lyrics_social.matching import all_candidates, rank_candidates
from lyrics_social.review import write_review_html
from lyrics_social.text_embeddings import compute_text_embeddings, resolve_device


def main():
    ap = argparse.ArgumentParser(description="Asocia frases de una letra con imagenes y compone piezas para redes.")
    ap.add_argument("--images", required=True, help="Carpeta generada por selector-fotogramas (con metadata.json)")
    ap.add_argument("--lyrics", required=True, help="Archivo de texto con una frase por linea")
    ap.add_argument(
        "--favorites",
        help="Respaldo JSON del visor de selector-fotogramas (con 'favorites'); "
             "si se pasa, solo se consideran esos fotogramas",
    )
    ap.add_argument("--output", help="Carpeta de salida (default: <images>/creator)")
    ap.add_argument("--format", default="instagram_4_5", choices=sorted(FORMATS))
    ap.add_argument(
        "--selection-mode", default="auto", choices=["auto", "manual"],
        help="'auto' (default): el algoritmo elige las top-k fotos mas afines por frase. "
             "'manual': todas las fotos quedan disponibles como candidatas en todas las "
             "frases, para que el usuario las compare a mano en review.html",
    )
    ap.add_argument("--top-k", type=int, default=5, help="Candidatas a guardar por frase (solo modo 'auto')")
    ap.add_argument("--clip-model", default="ViT-B-32")
    ap.add_argument("--clip-pretrained", default="laion2b_s34b_b79k")
    ap.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda", "mps"])
    args = ap.parse_args()

    lines = load_lines(args.lyrics)
    if not lines:
        sys.exit(f"{args.lyrics} no tiene frases.")

    images_dir, frames, image_embeddings = load_image_library(args.images, favorites_path=args.favorites)
    frames_by_id = {f["id"]: f for f in frames}
    if args.favorites:
        print(f"Filtrado a favoritos: {len(frames)} fotogramas ({args.favorites})")

    output_dir = Path(args.output).resolve() if args.output else images_dir / "creator"
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.selection_mode == "manual":
        print(
            f"Modo manual: las {len(frames)} fotos quedan disponibles como "
            f"candidatas en cada una de las {len(lines)} frases (sin rankear)."
        )
        results = all_candidates(lines, frames)
    else:
        device = resolve_device(args.device)
        print(f"Calculando embeddings de texto ({len(lines)} frases) en device={device}...")
        line_embeddings = compute_text_embeddings(lines, args.clip_model, args.clip_pretrained, device)

        print("Rankeando candidatas por frase...")
        results = rank_candidates(lines, line_embeddings, frames, image_embeddings, args.top_k)

    n_candidates = sum(len(r["candidates"]) for r in results)
    print(f"Componiendo formato {args.format} ({n_candidates} candidatas)...")
    copied_sources = {}  # image_id -> ruta relativa ya copiada, evita duplicar copias
    copied_thumbs = {}  # idem, solo modo manual: reusa la miniatura en vez de hornear cada combinacion
    for result in results:
        line_idx = result["index"] + 1
        for candidate in result["candidates"]:
            frame = frames_by_id[candidate["image_id"]]
            image_id = candidate["image_id"]
            full_src = frame_full_path(images_dir, frame)

            # Copia la foto original (sin recortar) para que review.html pueda
            # recortarla/posicionarla en vivo en el navegador (ver initDrag/drawCover).
            if image_id not in copied_sources:
                source_path = f"sources/{image_id:05d}{full_src.suffix}"
                dest = output_dir / source_path
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(full_src, dest)
                copied_sources[image_id] = source_path

            candidate["source"] = copied_sources[image_id]
            candidate["face_position"] = frame.get("face_position")
            candidate["text_anchor"] = text_anchor(frame)

            if args.selection_mode == "manual":
                # Con TODAS las fotos como candidatas en TODAS las frases, hornear
                # una composicion con texto por cada combinacion frase x foto seria
                # combinatoriamente carisimo; se reutiliza la miniatura de
                # selector-fotogramas como preview del candidato (una copia por foto).
                if image_id not in copied_thumbs:
                    thumb_src = Path(images_dir) / frame["thumb"]
                    thumb_rel = f"thumbs/{image_id:05d}{thumb_src.suffix}"
                    thumb_dest = output_dir / thumb_rel
                    thumb_dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(thumb_src, thumb_dest)
                    copied_thumbs[image_id] = thumb_rel
                candidate["composed"] = copied_thumbs[image_id]
                candidate["background"] = None
            else:
                thumb_path = f"compositions/{line_idx:03d}_{image_id}.jpg"
                bg_path = f"backgrounds/{line_idx:03d}_{image_id}.jpg"
                compose(
                    image_path=full_src,
                    text=result["line"],
                    frame=frame,
                    format_name=args.format,
                    output_path=output_dir / thumb_path,
                )
                compose_background(
                    image_path=full_src,
                    frame=frame,
                    format_name=args.format,
                    output_path=output_dir / bg_path,
                )
                candidate["composed"] = thumb_path
                candidate["background"] = bg_path

    associations = {
        "lyrics_source": str(Path(args.lyrics).resolve()),
        "images_source": str(images_dir),
        "format": args.format,
        "lines": results,
    }
    (output_dir / "associations.json").write_text(json.dumps(associations, indent=2, ensure_ascii=False))

    write_review_html(output_dir, results, format_name=args.format, images_source=images_dir)

    print(f"\nListo. Abre {output_dir / 'review.html'} en tu navegador.")
    print(f"{len(lines)} frases procesadas -> {output_dir}")


if __name__ == "__main__":
    main()
