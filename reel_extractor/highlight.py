"""Combina las senales de audio y visual en una sola linea de tiempo, y elige
las N mejores ventanas no superpuestas (los "reels") de duracion fija."""
import numpy as np


def combine_and_score(audio_times, audio_scores, visual_times, visual_scores, duration, audio_weight=0.5, grid_step=0.5):
    """Resamplea ambas senales a una grilla comun de tiempo (cada grid_step
    segundos) y las combina segun audio_weight (0 = solo visual, 1 = solo
    audio). Retorna (grid_times, combined_scores).
    """
    grid_times = np.arange(0.0, max(duration, grid_step), grid_step)

    audio_on_grid = (
        np.zeros_like(grid_times) if len(audio_times) < 2
        else np.interp(grid_times, audio_times, audio_scores)
    )
    visual_on_grid = (
        np.zeros_like(grid_times) if len(visual_times) < 2
        else np.interp(grid_times, visual_times, visual_scores)
    )

    combined = audio_weight * audio_on_grid + (1 - audio_weight) * visual_on_grid
    return grid_times, combined


def pick_windows(grid_times, combined, window_duration, n_reels, min_gap=1.0, step=1.0):
    """Elige hasta n_reels ventanas de largo window_duration que maximizan el
    score promedio dentro de la ventana, sin superponerse (con margen minimo
    min_gap entre ventanas aceptadas). Estrategia greedy: ordena candidatas
    por score y acepta la primera que no se superponga con las ya elegidas
    (mismo patron greedy que cluster_and_select en video_processor/generate.py).

    Retorna lista de dicts {"start", "end", "score"} ordenada por tiempo.
    """
    if len(grid_times) == 0:
        return []

    video_duration = float(grid_times[-1])
    if video_duration <= window_duration:
        return [{"start": 0.0, "end": video_duration, "score": float(combined.mean())}]

    grid_step = grid_times[1] - grid_times[0] if len(grid_times) > 1 else 0.5
    window_n = max(1, int(round(window_duration / grid_step)))

    candidates = []
    for s in np.arange(0.0, video_duration - window_duration, step):
        idx_start = int(round(s / grid_step))
        idx_end = min(len(combined), idx_start + window_n)
        if idx_end <= idx_start:
            continue
        window_score = float(combined[idx_start:idx_end].mean())
        candidates.append({"start": float(s), "end": float(s) + window_duration, "score": window_score})

    candidates.sort(key=lambda w: w["score"], reverse=True)

    selected = []
    for cand in candidates:
        overlaps = any(
            cand["start"] < sel["end"] + min_gap and cand["end"] > sel["start"] - min_gap
            for sel in selected
        )
        if not overlaps:
            selected.append(cand)
        if len(selected) >= n_reels:
            break

    selected.sort(key=lambda w: w["start"])
    return selected
