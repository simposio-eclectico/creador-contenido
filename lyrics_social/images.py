"""Carga de la libreria de imagenes producida por selector-fotogramas.

Espera una carpeta de salida de `selector-fotogramas/generate.py`, es decir
con `metadata.json` y `full/` dentro. Requiere que metadata.json incluya el
campo "embedding" por fotograma (agregado en la version del schema que
exporta OpenCLIP + face_bbox/brightness).
"""
import json
import sys
from pathlib import Path

import numpy as np


def load_favorite_ids(backup_path):
    """Lee un respaldo JSON exportado por el visor de selector-fotogramas
    (boton 'Descargar respaldo JSON' / respaldo automatico) y devuelve el
    set de ids marcados como favoritos."""
    backup_path = Path(backup_path)
    backup = json.loads(backup_path.read_text())
    favorites = backup.get("favorites")
    if favorites is None:
        sys.exit(f"{backup_path} no tiene una lista 'favorites'. ¿Es un respaldo de selector-fotogramas?")
    return set(favorites)


def load_image_library(images_dir, favorites_path=None):
    images_dir = Path(images_dir)
    metadata_path = images_dir / "metadata.json"
    if not metadata_path.exists():
        sys.exit(
            f"No se encontro {metadata_path}. "
            "Se espera una carpeta generada por selector-fotogramas/generate.py."
        )

    metadata = json.loads(metadata_path.read_text())
    frames = metadata.get("frames", [])
    if not frames:
        sys.exit(f"{metadata_path} no tiene fotogramas ('frames' vacio).")

    if "embedding" not in frames[0]:
        sys.exit(
            "El metadata.json no incluye 'embedding' por fotograma. "
            "Regenera la carpeta con una version de selector-fotogramas que "
            "exporte embeddings OpenCLIP en metadata.json."
        )

    if favorites_path is not None:
        favorite_ids = load_favorite_ids(favorites_path)
        frames = [f for f in frames if f["id"] in favorite_ids]
        if not frames:
            sys.exit(f"Ningun fotograma de {metadata_path} coincide con los favoritos de {favorites_path}.")

    embeddings = np.array([f["embedding"] for f in frames], dtype=np.float32)
    return images_dir, frames, embeddings


def frame_full_path(images_dir, frame):
    return Path(images_dir) / frame["full"]
