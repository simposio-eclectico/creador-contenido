"""Muestrea frames del video y calcula un score visual (entropia, contraste,
saliencia y movimiento entre frames), usado como la otra senal (junto a
audio_signal) para detectar los momentos mas destacados de un video."""
import numpy as np
from tqdm import tqdm

from ._ffmpeg_utils import run


def sample_frames_for_analysis(input_path, tmp_dir, fps=2.0):
    """Muestrea el video a baja tasa (default 2fps) para analisis visual barato."""
    tmp_dir.mkdir(parents=True, exist_ok=True)
    pattern = str(tmp_dir / "%06d.jpg")
    run([
        "ffmpeg", "-y", "-i", str(input_path),
        "-vf", f"fps={fps}",
        "-q:v", "4",
        pattern,
    ])
    frames = sorted(tmp_dir.glob("*.jpg"))
    times = [i / fps for i in range(len(frames))]
    return frames, times


def compute_visual_scores(frame_paths):
    """Calcula entropia, contraste, saliencia (mismas metricas que
    video_processor/generate.py) mas movimiento (diff frame a frame, senal
    nueva no presente en video_processor porque ese modulo analiza frames
    aislados, no una secuencia temporal).

    Retorna (scores, metrics_dict) normalizado 0-1.
    """
    import cv2

    sal_detector = cv2.saliency.StaticSaliencySpectralResidual_create()
    entropy, contrast, saliency, motion = [], [], [], []
    prev_gray = None

    for p in tqdm(frame_paths, desc="Metricas visuales (reels)"):
        bgr = cv2.imread(str(p))
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        entropy.append(_entropy_of(gray))
        contrast.append(float(cv2.Laplacian(gray, cv2.CV_64F).var()))
        saliency.append(_saliency_score(sal_detector, bgr))
        motion.append(0.0 if prev_gray is None else float(cv2.absdiff(gray, prev_gray).mean()))
        prev_gray = gray

    metrics = {
        "entropy": np.array(entropy),
        "contrast": np.array(contrast),
        "saliency": np.array(saliency),
        "motion": np.array(motion),
    }

    scores = (
        0.35 * _minmax(metrics["entropy"])
        + 0.25 * _minmax(np.log1p(metrics["contrast"]))
        + 0.20 * _minmax(metrics["motion"])
        + 0.20 * _minmax(metrics["saliency"])
    )
    return scores, metrics


def _entropy_of(gray):
    hist = np.bincount(gray.flatten(), minlength=256).astype(np.float64)
    p = hist / hist.sum()
    p = p[p > 0]
    return float(-(p * np.log2(p)).sum())


def _saliency_score(sal_detector, bgr):
    ok, sal_map = sal_detector.computeSaliency(bgr)
    if not ok:
        return 0.0
    sal_map = (sal_map * 255).astype(np.uint8)
    thresh = np.percentile(sal_map, 90)
    hot = sal_map[sal_map >= thresh]
    return float(hot.mean()) if hot.size else float(sal_map.mean())


def _minmax(arr):
    lo, hi = arr.min(), arr.max()
    if hi - lo < 1e-9:
        return np.zeros_like(arr)
    return (arr - lo) / (hi - lo)
