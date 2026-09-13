"""Extrae la pista de audio y calcula un score de energia/flujo por ventana
de tiempo, usado como una de las dos senales (junto a visual_signal) para
detectar los momentos mas destacados de un video."""
import numpy as np

from ._ffmpeg_utils import run


def extract_audio_wav(input_path, out_wav):
    """Extrae audio mono a 22050Hz en WAV (formato simple para scipy.io.wavfile)."""
    run([
        "ffmpeg", "-y", "-i", str(input_path),
        "-ac", "1", "-ar", "22050", "-vn",
        str(out_wav),
    ])
    return out_wav


def compute_audio_scores(wav_path, win=0.5, hop=0.25):
    """Calcula RMS energy + flujo espectral (proxy simple para picos de
    volumen / risas / aplausos) sobre ventanas deslizantes.

    Retorna (times, scores) normalizado 0-1.
    """
    from scipy.io import wavfile

    sr, samples = wavfile.read(wav_path)
    samples = samples.astype(np.float64)
    if samples.ndim > 1:
        samples = samples.mean(axis=1)

    win_n = int(win * sr)
    hop_n = max(1, int(hop * sr))
    if win_n <= 0 or len(samples) < win_n:
        return np.array([0.0]), np.array([0.0])

    n_windows = max(1, (len(samples) - win_n) // hop_n + 1)
    rms = np.zeros(n_windows)
    times = np.zeros(n_windows)
    for i in range(n_windows):
        start = i * hop_n
        chunk = samples[start:start + win_n]
        rms[i] = np.sqrt(np.mean(chunk ** 2)) if len(chunk) else 0.0
        times[i] = (start + win_n / 2) / sr

    # Flujo: incremento de energia respecto a la ventana anterior (onset proxy)
    flux = np.zeros(n_windows)
    flux[1:] = np.maximum(0.0, rms[1:] - rms[:-1])

    scores = 0.6 * _minmax(rms) + 0.4 * _minmax(flux)
    return times, scores


def _minmax(arr):
    lo, hi = arr.min(), arr.max()
    if hi - lo < 1e-9:
        return np.zeros_like(arr)
    return (arr - lo) / (hi - lo)
