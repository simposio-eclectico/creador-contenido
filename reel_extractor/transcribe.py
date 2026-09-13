"""Transcribe el video completo una sola vez con Whisper (local, offline) y
genera archivos .srt recortados/re-alineados para cada ventana (reel).

Se transcribe una sola vez sobre el video completo en lugar de por-clip:
el overhead fijo de cargar el modelo domina en clips cortos, y los
timestamps de Whisper ya quedan en tiempo absoluto del video, asi que
recortar por ventana es solo un filtro + resta de offset, sin necesidad
de volver a alinear nada.
"""
from pathlib import Path


def transcribe_full_video(input_path, model_size="base", language="es"):
    """Carga Whisper y transcribe el video completo. Retorna una lista de
    segmentos [{"start", "end", "text"}] en tiempo absoluto del video."""
    import whisper

    model = whisper.load_model(model_size)
    result = model.transcribe(str(input_path), language=language, verbose=False)
    return [
        {"start": float(seg["start"]), "end": float(seg["end"]), "text": seg["text"].strip()}
        for seg in result["segments"]
    ]


def segments_for_window(segments, window_start, window_end):
    """Filtra los segmentos que caen (parcial o totalmente) dentro de
    [window_start, window_end], recorta sus bordes a la ventana y resta
    window_start para re-zerar los timestamps al inicio del clip."""
    out = []
    for seg in segments:
        if seg["end"] <= window_start or seg["start"] >= window_end:
            continue
        start = max(seg["start"], window_start) - window_start
        end = min(seg["end"], window_end) - window_start
        if end <= start:
            continue
        out.append({"start": start, "end": end, "text": seg["text"]})
    return out


def _format_srt_timestamp(seconds):
    seconds = max(0.0, seconds)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def segments_to_srt(segments):
    """Convierte una lista de segmentos [{"start","end","text"}] (ya en
    tiempo relativo al clip) al formato de texto .srt estandar."""
    lines = []
    for i, seg in enumerate(segments, start=1):
        lines.append(str(i))
        lines.append(f"{_format_srt_timestamp(seg['start'])} --> {_format_srt_timestamp(seg['end'])}")
        lines.append(seg["text"])
        lines.append("")
    return "\n".join(lines)


def write_srt(segments, out_path):
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(segments_to_srt(segments), encoding="utf-8")
    return out_path
