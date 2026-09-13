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
from reel_extractor.highlight import combine_and_score, pick_windows
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
    args = ap.parse_args()

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

    reels = [
        {"id": i + 1, "start": round(w["start"], 2), "end": round(w["end"], 2), "score": round(w["score"], 4)}
        for i, w in enumerate(windows)
    ]

    metadata = {
        "source": input_path.name,
        "duration": duration,
        "requested_duration": args.duration,
        "requested_count": args.count,
        "audio_weight": args.audio_weight,
        "reels": reels,
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False))

    print(f"\n{len(reels)} reel(s) detectado(s):")
    for r in reels:
        print(f"  #{r['id']}: {r['start']}s - {r['end']}s (score {r['score']})")
    print(f"\nMetadata escrita en {output_dir / 'metadata.json'}")


if __name__ == "__main__":
    main()
