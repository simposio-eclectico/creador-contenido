#!/usr/bin/env python3
"""
extract.py - Detecta y extrae los momentos mas destacados ("reels") de un video.

Pipeline:
  1. Extrae la pista de audio y calcula un score de energia/flujo por ventana
     de tiempo (audio_signal.py).
  2. Muestrea el video a baja tasa y calcula un score visual: entropia,
     contraste, saliencia y movimiento entre frames (visual_signal.py).
  3. Combina ambas senales segun --audio-weight (0=solo visual, 1=solo audio)
     y elige las --count mejores ventanas no superpuestas de --duration
     segundos (highlight.py).
  4. (Fase 2) Renderiza cada ventana como clip vertical con ffmpeg.
  5. (Fase 3) Si --subtitles, transcribe con Whisper y genera .srt +
     version con subtitulos quemados.

Uso:
  python3 extract.py --input video.mp4 --output ./reels_output \
      --duration 30 --count 3 --audio-weight 0.5
"""
import argparse
import json
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from reel_extractor._ffmpeg_utils import probe_duration
from reel_extractor.audio_signal import compute_audio_scores, extract_audio_wav
from reel_extractor.clip_render import FORMATS, apply_fade, burn_subtitles, render_vertical_clip
from reel_extractor.fonts import FONT_CATALOG
from reel_extractor.highlight import combine_and_score, pick_windows
from reel_extractor.transcribe import segments_for_window, transcribe_full_video, write_srt
from reel_extractor.visual_signal import compute_visual_scores, sample_frames_for_analysis


def main():
    ap = argparse.ArgumentParser(description="Extrae los momentos mas destacados de un video como reels.")
    ap.add_argument("--input", required=True, help="Ruta al video de entrada")
    ap.add_argument("--output", required=True, help="Carpeta de salida (se crea si no existe)")
    ap.add_argument("--duration", type=int, default=30, help="Duracion de cada reel en segundos (15-60)")
    ap.add_argument("--count", type=int, default=3, help="Cantidad de reels a extraer")
    ap.add_argument(
        "--audio-weight", type=float, default=0.5,
        help="Peso del audio vs. visual al detectar highlights (0=solo visual, 1=solo audio)",
    )
    ap.add_argument("--visual-fps", type=float, default=2.0, help="Fps de muestreo para analisis visual")
    ap.add_argument("--min-gap", type=float, default=1.0, help="Segundos minimos entre reels elegidos")
    ap.add_argument("--format", default="story", choices=sorted(FORMATS), help="Formato vertical de salida")
    ap.add_argument("--subtitles", action="store_true", help="Genera subtitulos (.srt + quemados) con Whisper")
    ap.add_argument("--whisper-model", default="base", choices=["tiny", "base", "small"])
    ap.add_argument("--language", default="es", help="Idioma para Whisper (default 'es')")
    ap.add_argument(
        "--subtitle-font", default="im_fell", choices=sorted(FONT_CATALOG),
        help="Tipografia para quemar subtitulos (default 'im_fell')",
    )
    ap.add_argument(
        "--fade-out", type=float, default=0.0,
        help="Segundos de fadeout de audio/video al final de cada reel (0 = desactivado)",
    )
    ap.add_argument(
        "--fade-target", default="black", choices=["black", "image"],
        help="'black': fade a negro. 'image': disuelve hacia --fade-image",
    )
    ap.add_argument("--fade-image", help="Ruta a imagen fija para --fade-target=image")
    ap.add_argument(
        "--fade-image-fit", default="cover", choices=["cover", "contain-width", "contain-height"],
        help="Como ajustar la imagen en --fade-target=image (default 'cover')",
    )
    ap.add_argument(
        "--fade-background-color", default="black",
        help="Color de fondo para --fade-target=image en modo contain (ej: 'black', 'ffffff', default 'black')",
    )
    ap.add_argument(
        "--skip-burn", action="store_true",
        help="Genera .srt y guarda los segmentos en metadata.json pero NO quema "
             "los subtitulos todavia (para permitir editarlos antes, ver burn_subs.py)",
    )
    args = ap.parse_args()

    if args.fade_out and args.fade_target == "image" and not args.fade_image:
        sys.exit("--fade-target=image requiere --fade-image")

    if not 15 <= args.duration <= 60:
        sys.exit("--duration debe estar entre 15 y 60 segundos")
    if not 0.0 <= args.audio_weight <= 1.0:
        sys.exit("--audio-weight debe estar entre 0.0 y 1.0")

    input_path = Path(args.input).resolve()
    output_dir = Path(args.output).resolve()
    if not input_path.exists():
        sys.exit(f"No existe el archivo de entrada: {input_path}")
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Analizando '{input_path.name}'...")
    duration = probe_duration(input_path)
    print(f"Duracion del video: {duration:.1f}s")

    with tempfile.TemporaryDirectory(prefix="reel-extractor-") as tmp:
        tmp_dir = Path(tmp)

        print("Extrayendo audio y calculando score de energia/flujo...")
        wav_path = extract_audio_wav(input_path, tmp_dir / "audio.wav")
        audio_times, audio_scores = compute_audio_scores(wav_path)

        print(f"Muestreando video a {args.visual_fps} fps para analisis visual...")
        frames, visual_times = sample_frames_for_analysis(input_path, tmp_dir / "frames", args.visual_fps)
        visual_scores, _ = compute_visual_scores(frames)

        print(f"Combinando senales (audio_weight={args.audio_weight})...")
        grid_times, combined = combine_and_score(
            audio_times, audio_scores, visual_times, visual_scores,
            duration=duration, audio_weight=args.audio_weight,
        )

        print(f"Eligiendo {args.count} ventana(s) de {args.duration}s...")
        windows = pick_windows(grid_times, combined, args.duration, args.count, min_gap=args.min_gap)

    if not windows:
        sys.exit("No se pudo encontrar ninguna ventana valida en el video.")

    if len(windows) < args.count:
        print(f"Aviso: solo se encontraron {len(windows)} ventana(s) no superpuestas (se pidieron {args.count}).")

    transcript_segments = None
    if args.subtitles:
        print(f"Transcribiendo video completo con Whisper ({args.whisper_model})...")
        transcript_segments = transcribe_full_video(input_path, model_size=args.whisper_model, language=args.language)
        print(f"{len(transcript_segments)} segmento(s) transcritos.")

    clips_dir = output_dir / "clips"
    subs_dir = output_dir / "subs"
    reels = []
    for i, w in enumerate(windows):
        reel_id = i + 1
        print(f"Renderizando reel #{reel_id} ({args.format}, {w['start']:.1f}s-{w['end']:.1f}s)...")
        window_duration = w["end"] - w["start"]
        raw_clip_path = clips_dir / f"{reel_id:02d}_raw.mp4"
        render_vertical_clip(input_path, w["start"], w["end"], raw_clip_path, format_name=args.format)

        clip_path = clips_dir / f"{reel_id:02d}.mp4"
        if args.fade_out > 0:
            print(f"Aplicando fadeout ({args.fade_target}) en reel #{reel_id}...")
            apply_fade(
                raw_clip_path, clip_path, window_duration,
                fade_duration=min(args.fade_out, window_duration),
                fade_target=args.fade_target, fade_image_path=args.fade_image,
                format_name=args.format,
                image_fit=args.fade_image_fit,
                background_color=args.fade_background_color,
            )
            raw_clip_path.unlink()
        else:
            raw_clip_path.rename(clip_path)

        reel = {
            "id": reel_id,
            "start": round(w["start"], 2),
            "end": round(w["end"], 2),
            "score": round(w["score"], 4),
            "clip": f"clips/{clip_path.name}",
            "srt": None,
            "clip_with_subtitles": None,
            "segments": None,
        }

        if transcript_segments is not None:
            window_segments = segments_for_window(transcript_segments, w["start"], w["end"])
            srt_path = subs_dir / f"{reel_id:02d}.srt"
            write_srt(window_segments, srt_path)
            reel["srt"] = f"subs/{srt_path.name}"
            reel["segments"] = window_segments

            if args.skip_burn:
                print(f"Reel #{reel_id}: subtitulos generados, pendientes de revision (--skip-burn).")
            else:
                print(f"Quemando subtitulos en reel #{reel_id} (fuente: {args.subtitle_font})...")
                burned_path = clips_dir / f"{reel_id:02d}_subtitled.mp4"
                try:
                    burn_subtitles(clip_path, window_segments, burned_path, font_name=args.subtitle_font)
                    reel["clip_with_subtitles"] = f"clips/{burned_path.name}"
                except RuntimeError as exc:
                    print(
                        f"Aviso: no se pudo quemar subtitulos en reel #{reel_id} "
                        f"(revisa que ffmpeg tenga 'drawtext', requiere libfreetype). "
                        f"Se conserva el .srt. Detalle: {exc}"
                    )

        reels.append(reel)

    metadata = {
        "source": input_path.name,
        "duration": duration,
        "requested_duration": args.duration,
        "requested_count": args.count,
        "audio_weight": args.audio_weight,
        "format": args.format,
        "subtitle_font": args.subtitle_font,
        "fade_out": args.fade_out,
        "fade_target": args.fade_target if args.fade_out > 0 else None,
        "fade_image_fit": args.fade_image_fit if args.fade_out > 0 else None,
        "fade_background_color": args.fade_background_color if args.fade_out > 0 else None,
        "subtitles_pending_review": bool(args.subtitles and args.skip_burn),
        "reels": reels,
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False))

    print(f"\n{len(reels)} reel(s) generado(s):")
    for r in reels:
        print(f"  #{r['id']}: {r['start']}s - {r['end']}s (score {r['score']}) -> {r['clip']}")
    print(f"\nMetadata escrita en {output_dir / 'metadata.json'}")


if __name__ == "__main__":
    main()
