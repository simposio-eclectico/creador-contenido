#!/usr/bin/env python3
"""
generate.py - Convierte un videoclip en una hoja de contactos navegable.

Pipeline:
  1. Muestreo uniforme del video con ffmpeg (candidatos, p.ej. 4 fps).
  2. Metricas visuales por candidato (entropia, contraste, saliencia, exposicion)
     y deteccion de picos de luminancia (flash).
  3. Embeddings OpenCLIP + clustering (DBSCAN) para eliminar casi-duplicados,
     quedandonos con el mejor fotograma de cada grupo.
  4. Deteccion de rostros (Haar Cascade) sobre los representantes finales,
     con posicion normalizada (para pipelines de composicion externos).
  5. Extraccion de una rafaga de fotogramas de alta frecuencia (+-0.5s) alrededor
     de cada representante, para el modo de comparacion J/L en el visor.
  6. Genera thumbs/ (webp), full/ (jpg), metadata.json/metadata.js y copia el
     visor HTML/JS/CSS al directorio de salida, que es autocontenido.

Uso:
  python3 generate.py --input clip.mp4 --output ./mi-video-review
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image
from tqdm import tqdm

SCRIPT_DIR = Path(__file__).resolve().parent
VIEWER_DIR = SCRIPT_DIR / "viewer"


# --------------------------------------------------------------------------
# Utilidades de proceso / ffmpeg
# --------------------------------------------------------------------------

def run(cmd):
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Comando fallido: {' '.join(cmd)}\n{result.stderr}")
    return result.stdout


def probe_duration(input_path):
    out = run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(input_path),
    ])
    return float(out.strip())


def extract_candidates(input_path, raw_dir, fps):
    raw_dir.mkdir(parents=True, exist_ok=True)
    pattern = str(raw_dir / "%06d.jpg")
    run([
        "ffmpeg", "-y", "-i", str(input_path),
        "-vf", f"fps={fps}",
        "-q:v", "2",
        pattern,
    ])
    return sorted(raw_dir.glob("*.jpg"))


def extract_burst(input_path, out_dir, center_time, window, burst_fps):
    out_dir.mkdir(parents=True, exist_ok=True)
    start = max(0.0, center_time - window)
    duration = window * 2
    pattern = str(out_dir / "%03d.jpg")
    run([
        "ffmpeg", "-y", "-ss", f"{start:.3f}", "-i", str(input_path),
        "-t", f"{duration:.3f}", "-vf", f"fps={burst_fps}",
        "-q:v", "3",
        pattern,
    ])
    frames = sorted(out_dir.glob("*.jpg"))
    times = [start + i / burst_fps for i in range(len(frames))]
    return frames, times


# --------------------------------------------------------------------------
# Metricas visuales
# --------------------------------------------------------------------------

def entropy_of(gray):
    hist = np.bincount(gray.flatten(), minlength=256).astype(np.float64)
    p = hist / hist.sum()
    p = p[p > 0]
    return float(-(p * np.log2(p)).sum())


def saliency_score(sal_detector, bgr):
    ok, sal_map = sal_detector.computeSaliency(bgr)
    if not ok:
        return 0.0
    sal_map = (sal_map * 255).astype(np.uint8)
    thresh = np.percentile(sal_map, 90)
    hot = sal_map[sal_map >= thresh]
    return float(hot.mean()) if hot.size else float(sal_map.mean())


def compute_metrics(frame_paths):
    import cv2

    sal_detector = cv2.saliency.StaticSaliencySpectralResidual_create()
    entropy, contrast, saliency, luminance, exposure_std = [], [], [], [], []

    for p in tqdm(frame_paths, desc="Metricas visuales"):
        bgr = cv2.imread(str(p))
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        entropy.append(entropy_of(gray))
        contrast.append(float(cv2.Laplacian(gray, cv2.CV_64F).var()))
        saliency.append(saliency_score(sal_detector, bgr))
        luminance.append(float(gray.mean()))
        exposure_std.append(float(gray.std()))

    return {
        "entropy": np.array(entropy),
        "contrast": np.array(contrast),
        "saliency": np.array(saliency),
        "luminance": np.array(luminance),
        "exposure_std": np.array(exposure_std),
    }


def minmax(arr):
    lo, hi = arr.min(), arr.max()
    if hi - lo < 1e-9:
        return np.zeros_like(arr)
    return (arr - lo) / (hi - lo)


def composite_score(metrics):
    entropy_n = minmax(metrics["entropy"])
    contrast_n = minmax(np.log1p(metrics["contrast"]))
    saliency_n = minmax(metrics["saliency"])
    exposure_n = minmax(metrics["exposure_std"])
    score = 0.30 * entropy_n + 0.25 * contrast_n + 0.30 * saliency_n + 0.15 * exposure_n
    return score * 10.0  # escala 0-10 legible


def detect_flashes(luminance, fps):
    from scipy.signal import find_peaks

    if len(luminance) < 3:
        return set()
    prominence = max(5.0, luminance.std() * 0.75)
    peaks, _ = find_peaks(luminance, prominence=prominence, distance=max(1, int(fps * 0.3)))
    return set(int(i) for i in peaks)


# --------------------------------------------------------------------------
# Embeddings CLIP + clustering
# --------------------------------------------------------------------------

def compute_clip_embeddings(frame_paths, model_name, pretrained, device, batch_size=32):
    import torch
    import open_clip

    model, _, preprocess = open_clip.create_model_and_transforms(model_name, pretrained=pretrained)
    model.eval().to(device)

    feats = []
    with torch.no_grad():
        for i in tqdm(range(0, len(frame_paths), batch_size), desc="Embeddings CLIP"):
            batch_paths = frame_paths[i:i + batch_size]
            imgs = torch.stack([preprocess(Image.open(p).convert("RGB")) for p in batch_paths]).to(device)
            emb = model.encode_image(imgs)
            emb = emb / emb.norm(dim=-1, keepdim=True)
            feats.append(emb.cpu().numpy())
    return np.concatenate(feats, axis=0)


def cluster_and_select(embeddings, scores, eps, min_samples):
    from sklearn.cluster import DBSCAN

    labels = DBSCAN(eps=eps, min_samples=min_samples, metric="cosine").fit_predict(embeddings)
    clusters = {}
    selected = []
    next_noise_cluster = labels.max() + 1 if len(labels) else 0

    for idx, label in enumerate(labels):
        if label == -1:
            label = next_noise_cluster
            next_noise_cluster += 1
        clusters.setdefault(label, []).append(idx)

    for label, idxs in clusters.items():
        best_idx = max(idxs, key=lambda i: scores[i])
        selected.append((best_idx, label))

    return selected  # lista de (indice_candidato, cluster_id)


def resolve_device(requested):
    import torch

    if requested != "auto":
        return requested
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


# --------------------------------------------------------------------------
# Rostros (Haar Cascade de OpenCV; se descarga una vez si el paquete
# instalado no trae los archivos de datos, como ocurre en algunas builds).
# --------------------------------------------------------------------------

CASCADE_URL = "https://raw.githubusercontent.com/opencv/opencv/4.x/data/haarcascades/haarcascade_frontalface_default.xml"
CASCADE_CACHE = Path.home() / ".cache" / "contact-sheet-review" / "haarcascade_frontalface_default.xml"


def resolve_cascade_path():
    import cv2

    bundled = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
    if bundled.exists():
        return bundled

    if CASCADE_CACHE.exists():
        return CASCADE_CACHE

    try:
        import urllib.request

        print("Descargando detector de rostros (una sola vez)...")
        CASCADE_CACHE.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(CASCADE_URL, CASCADE_CACHE)
        return CASCADE_CACHE
    except Exception as exc:
        print(f"Aviso: no se pudo obtener el detector de rostros ({exc}). Se omite deteccion de rostros.")
        return None


def detect_faces(image_paths):
    """Para cada imagen, devuelve (bboxes_normalizados, posicion_cara_principal).

    bboxes_normalizados: lista de [x, y, w, h] en fraccion 0-1 del tamano de imagen.
    posicion_cara_principal: [cx, cy] normalizado de la cara mas grande, o None.
    """
    import cv2

    cascade_path = resolve_cascade_path()
    if cascade_path is None:
        return [([], None) for _ in image_paths]

    classifier = cv2.CascadeClassifier(str(cascade_path))
    results = []
    for p in tqdm(image_paths, desc="Deteccion de rostros"):
        img = cv2.imread(str(p))
        h_img, w_img = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = classifier.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40))

        bboxes = [
            [round(x / w_img, 4), round(y / h_img, 4), round(w / w_img, 4), round(h / h_img, 4)]
            for (x, y, w, h) in faces
        ]
        position = None
        if len(faces):
            x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
            position = [round((x + w / 2) / w_img, 4), round((y + h / 2) / h_img, 4)]

        results.append((bboxes, position))
    return results


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Genera una hoja de contactos navegable a partir de un video.")
    ap.add_argument("--input", required=True, help="Ruta al video de entrada")
    ap.add_argument("--output", required=True, help="Carpeta de salida (se crea si no existe)")
    ap.add_argument("--fps", type=float, default=4.0, help="Fps de muestreo de candidatos (default 4)")
    ap.add_argument("--thumb-width", type=int, default=320)
    ap.add_argument("--jpg-quality", type=int, default=90)
    ap.add_argument("--cluster-eps", type=float, default=0.08, help="Distancia coseno para DBSCAN")
    ap.add_argument("--cluster-min-samples", type=int, default=1)
    ap.add_argument("--clip-model", default="ViT-B-32")
    ap.add_argument("--clip-pretrained", default="laion2b_s34b_b79k")
    ap.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda", "mps"])
    ap.add_argument("--no-faces", action="store_true", help="Desactiva deteccion de rostros (Haar cascade)")
    ap.add_argument("--no-burst", action="store_true", help="Desactiva extraccion de rafagas +-0.5s")
    ap.add_argument("--burst-window", type=float, default=0.5, help="Segundos a cada lado del representante")
    ap.add_argument("--burst-fps", type=float, default=12.0)
    args = ap.parse_args()

    input_path = Path(args.input).resolve()
    output_dir = Path(args.output).resolve()
    if not input_path.exists():
        sys.exit(f"No existe el archivo de entrada: {input_path}")

    thumbs_dir = output_dir / "thumbs"
    full_dir = output_dir / "full"
    bursts_dir = full_dir / "bursts"
    selected_dir = output_dir / "selected"
    for d in (thumbs_dir, full_dir, selected_dir):
        d.mkdir(parents=True, exist_ok=True)

    print(f"Analizando '{input_path.name}'...")
    duration = probe_duration(input_path)
    print(f"Duracion: {duration:.1f}s")

    with tempfile.TemporaryDirectory(prefix="contact-sheet-") as tmp:
        raw_dir = Path(tmp) / "raw"
        print("Extrayendo candidatos...")
        candidates = extract_candidates(input_path, raw_dir, args.fps)
        times = [i / args.fps for i in range(len(candidates))]
        print(f"{len(candidates)} candidatos muestreados a {args.fps} fps")

        metrics = compute_metrics(candidates)
        scores = composite_score(metrics)
        flash_idx = detect_flashes(metrics["luminance"], args.fps)

        device = resolve_device(args.device)
        print(f"Calculando embeddings CLIP en device={device}...")
        embeddings = compute_clip_embeddings(candidates, args.clip_model, args.clip_pretrained, device)

        print("Agrupando casi-duplicados (DBSCAN)...")
        selected = cluster_and_select(embeddings, scores, args.cluster_eps, args.cluster_min_samples)
        selected.sort(key=lambda t: times[t[0]])
        print(f"{len(candidates)} candidatos -> {len(selected)} fotogramas finales")

        records = []
        rep_paths = []
        for new_id, (cand_idx, cluster_id) in enumerate(tqdm(selected, desc="Copiando full/thumbs"), start=1):
            src = candidates[cand_idx]
            full_name = f"{new_id:05d}.jpg"
            thumb_name = f"{new_id:05d}.webp"
            full_path = full_dir / full_name
            thumb_path = thumbs_dir / thumb_name

            img = Image.open(src).convert("RGB")
            img.save(full_path, quality=args.jpg_quality)
            w, h = img.size
            thumb_h = round(h * (args.thumb_width / w))
            img.resize((args.thumb_width, thumb_h)).save(thumb_path, "WEBP", quality=85)

            rep_paths.append(full_path)
            records.append({
                "id": new_id,
                "time": round(times[cand_idx], 3),
                "thumb": f"thumbs/{thumb_name}",
                "full": f"full/{full_name}",
                "score": round(float(scores[cand_idx]), 2),
                "entropy": round(float(metrics["entropy"][cand_idx]), 2),
                "contrast": round(float(metrics["contrast"][cand_idx]), 2),
                "saliency": round(float(metrics["saliency"][cand_idx]), 2),
                "brightness": round(float(metrics["luminance"][cand_idx] / 255.0), 3),
                "orientation": "landscape" if w > h else ("portrait" if h > w else "square"),
                "cluster": int(cluster_id),
                "flash": bool(cand_idx in flash_idx),
                "face": False,
                "face_count": 0,
                "face_bbox": [],
                "face_position": None,
                "embedding": [round(float(v), 5) for v in embeddings[cand_idx]],
                "burst": [],
            })

        if not args.no_faces:
            print("Detectando rostros en fotogramas finales...")
            face_data = detect_faces(rep_paths)
            for rec, (bboxes, position) in zip(records, face_data):
                rec["face"] = len(bboxes) > 0
                rec["face_count"] = len(bboxes)
                rec["face_bbox"] = bboxes
                rec["face_position"] = position

        if not args.no_burst:
            print("Extrayendo rafagas +-%.2fs por fotograma..." % args.burst_window)
            for rec in tqdm(records, desc="Rafagas"):
                burst_out = bursts_dir / f"{rec['id']:05d}"
                frames, btimes = extract_burst(
                    input_path, burst_out, rec["time"], args.burst_window, args.burst_fps,
                )
                rec["burst"] = [
                    {
                        "time": round(t, 3),
                        "path": f"full/bursts/{rec['id']:05d}/{f.name}",
                    }
                    for f, t in zip(frames, btimes)
                ]

    metadata = {
        "source": input_path.name,
        "duration": duration,
        "sample_fps": args.fps,
        "frames": records,
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))

    # metadata.js alimenta el visor en el navegador: se omite "embedding" (pesado,
    # 512 floats por fotograma) porque el visor no lo usa. metadata.json completo
    # es el que consumen pipelines externos (p.ej. matching imagen-texto).
    light_frames = [{k: v for k, v in rec.items() if k != "embedding"} for rec in records]
    light_metadata = {**metadata, "frames": light_frames}
    (output_dir / "metadata.js").write_text("window.METADATA = " + json.dumps(light_metadata) + ";")

    for fname in ("index.html", "app.js", "style.css"):
        shutil.copy(VIEWER_DIR / fname, output_dir / fname)

    print(f"\nListo. Abre {output_dir / 'index.html'} en tu navegador.")
    print(f"{len(records)} fotogramas finales de {len(candidates)} candidatos analizados.")


if __name__ == "__main__":
    main()
