#!/usr/bin/env python3
"""
generate_from_folder.py - Convierte una carpeta de fotos en una galería lista para main.py

Procesa una carpeta de fotos que no ha sido procesada anteriormente,
generando la estructura de metadata (con embeddings) requerida por main.py.

Pipeline:
  1. Carga todas las imágenes de la carpeta (JPG, PNG, WEBP, etc).
  2. Metricas visuales por imagen (entropia, contraste, saliencia, exposicion)
     y deteccion de picos de luminancia (flash).
  3. Embeddings OpenCLIP + clustering (DBSCAN) para eliminar casi-duplicados.
  4. Deteccion de rostros (Haar Cascade) sobre los representantes finales.
  5. Genera thumbs/ (webp), full/ (jpg), metadata.json/metadata.js, compatible
     con main.py (crea la estructura de selector-fotogramas).

Uso:
  python3 generate_from_folder.py --input /ruta/a/carpeta/fotos --output ./mi-galeria

Luego usa el output con main.py:
  python3 main.py --images ./mi-galeria --lyrics letra.txt --format instagram_4_5
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from tqdm import tqdm

SCRIPT_DIR = Path(__file__).resolve().parent
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}


# --------------------------------------------------------------------------
# Carga de imágenes
# --------------------------------------------------------------------------

def load_images_from_folder(folder_path):
    """Carga todas las imágenes de una carpeta en orden alfabético."""
    folder = Path(folder_path)
    image_paths = []

    for ext in IMAGE_EXTENSIONS:
        image_paths.extend(sorted(folder.glob(f"*{ext}")))
        image_paths.extend(sorted(folder.glob(f"*{ext.upper()}")))

    # Elimina duplicados manteniendo orden
    seen = set()
    unique_paths = []
    for p in image_paths:
        resolved = p.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique_paths.append(resolved)

    return unique_paths


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
    return score * 10.0


def detect_flashes(luminance, threshold=None):
    """Detecta flashes (picos de luminancia)."""
    if len(luminance) < 3:
        return set()

    if threshold is None:
        threshold = luminance.mean() + (luminance.std() * 2.0)

    flashes = set()
    for i, val in enumerate(luminance):
        if val > threshold:
            flashes.add(i)

    return flashes


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

    return selected


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
# Detección de rostros (Haar Cascade)
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
    """Para cada imagen, devuelve (bboxes_normalizados, posicion_cara_principal)."""
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
    ap = argparse.ArgumentParser(description="Procesa una carpeta de fotos para usarla con main.py")
    ap.add_argument("--input", required=True, help="Ruta a la carpeta de fotos")
    ap.add_argument("--output", required=True, help="Carpeta de salida (se crea si no existe)")
    ap.add_argument("--thumb-width", type=int, default=320)
    ap.add_argument("--jpg-quality", type=int, default=90)
    ap.add_argument("--cluster-eps", type=float, default=0.08, help="Distancia coseno para DBSCAN (bajo=mas fotogramas)")
    ap.add_argument("--cluster-min-samples", type=int, default=1)
    ap.add_argument("--clip-model", default="ViT-B-32")
    ap.add_argument("--clip-pretrained", default="laion2b_s34b_b79k")
    ap.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda", "mps"])
    ap.add_argument("--no-faces", action="store_true", help="Desactiva deteccion de rostros")
    args = ap.parse_args()

    input_path = Path(args.input).resolve()
    output_dir = Path(args.output).resolve()

    if not input_path.is_dir():
        sys.exit(f"No existe la carpeta: {input_path}")

    print(f"Buscando imagenes en '{input_path}'...")
    images = load_images_from_folder(input_path)
    if not images:
        sys.exit(f"No se encontraron imagenes en: {input_path}")

    print(f"Encontradas {len(images)} imagenes")

    thumbs_dir = output_dir / "thumbs"
    full_dir = output_dir / "full"
    selected_dir = output_dir / "selected"
    for d in (thumbs_dir, full_dir, selected_dir):
        d.mkdir(parents=True, exist_ok=True)

    print("Calculando metricas visuales...")
    metrics = compute_metrics(images)
    scores = composite_score(metrics)
    flash_idx = detect_flashes(metrics["luminance"])

    device = resolve_device(args.device)
    print(f"Calculando embeddings CLIP en device={device}...")
    embeddings = compute_clip_embeddings(images, args.clip_model, args.clip_pretrained, device)

    print("Agrupando casi-duplicados (DBSCAN)...")
    selected = cluster_and_select(embeddings, scores, args.cluster_eps, args.cluster_min_samples)
    selected.sort(key=lambda t: t[0])
    print(f"{len(images)} imagenes -> {len(selected)} fotogramas finales")

    records = []
    rep_paths = []
    for new_id, (img_idx, cluster_id) in enumerate(tqdm(selected, desc="Copiando full/thumbs"), start=1):
        src = images[img_idx]
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
            "time": new_id - 1,
            "thumb": f"thumbs/{thumb_name}",
            "full": f"full/{full_name}",
            "score": round(float(scores[img_idx]), 2),
            "entropy": round(float(metrics["entropy"][img_idx]), 2),
            "contrast": round(float(metrics["contrast"][img_idx]), 2),
            "saliency": round(float(metrics["saliency"][img_idx]), 2),
            "brightness": round(float(metrics["luminance"][img_idx] / 255.0), 3),
            "orientation": "landscape" if w > h else ("portrait" if h > w else "square"),
            "cluster": int(cluster_id),
            "flash": bool(img_idx in flash_idx),
            "face": False,
            "face_count": 0,
            "face_bbox": [],
            "face_position": None,
            "embedding": [round(float(v), 5) for v in embeddings[img_idx]],
            "burst": [],
        })

    if not args.no_faces:
        print("Detectando rostros...")
        face_data = detect_faces(rep_paths)
        for rec, (bboxes, position) in zip(records, face_data):
            rec["face"] = len(bboxes) > 0
            rec["face_count"] = len(bboxes)
            rec["face_bbox"] = bboxes
            rec["face_position"] = position

    # Escribe metadata.json con embeddings (requerido por main.py)
    metadata = {
        "source": input_path.name,
        "duration": len(images),
        "sample_fps": 1,
        "frames": records,
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))

    # metadata.js para compatibilidad (sin embeddings)
    light_frames = [{k: v for k, v in rec.items() if k != "embedding"} for rec in records]
    light_metadata = {**metadata, "frames": light_frames}
    (output_dir / "metadata.js").write_text("window.METADATA = " + json.dumps(light_metadata) + ";")

    # Copia el visor HTML (opcional, por si se quiere revisar)
    viewer_dir = SCRIPT_DIR / "viewer"
    if viewer_dir.exists():
        for fname in ("index.html", "app.js", "style.css"):
            src = viewer_dir / fname
            if src.exists():
                shutil.copy(src, output_dir / fname)

    print(f"\nListo. Carpeta procesada: {output_dir}")
    print(f"{len(records)} fotogramas finales de {len(images)} imagenes.")
    print(f"\nAhora puedes usar con main.py:")
    print(f"  python3 main.py --images {output_dir} --lyrics letra.txt --format instagram_4_5")


if __name__ == "__main__":
    main()
