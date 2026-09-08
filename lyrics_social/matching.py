"""Ranking de imagenes candidatas por frase.

Estado actual: solo similitud CLIP (embeddings normalizados -> producto punto
= similitud coseno). Eso alcanza para relaciones "literales/semanticas": la
imagen que mas se parece conceptualmente a la frase.

Extension pendiente (no implementada aca a proposito): un paso con LLM que,
dado el texto de la frase y una descripcion/tags de las imagenes candidatas,
reclasifique cada par como semantica / asociativa / contrapunto en vez de
asumir que todo lo que rankea alto por CLIP es "semantica". Ese paso necesita
decidir primero que proveedor de LLM usar, asi que se deja como punto de
extension explicito: `classify_relation()` es el lugar para conectarlo.
"""
import numpy as np


def classify_relation(line, frame, clip_score):
    """Punto de extension: hoy siempre devuelve 'semantica' (similitud CLIP).

    Reemplazar/envolver esta funcion cuando se conecte el paso de LLM para
    distinguir asociativa/contrapunto.
    """
    return "semantica"


def rank_candidates(lines, line_embeddings, frames, image_embeddings, top_k):
    """Devuelve, por linea, hasta top_k candidatos ordenados por similitud."""
    # embeddings ya normalizados en origen (selector-fotogramas y text_embeddings)
    sims = line_embeddings @ image_embeddings.T  # (n_lineas, n_imagenes)

    results = []
    for i, line in enumerate(lines):
        line_sims = sims[i]
        order = np.argsort(-line_sims)[:top_k]
        pool = line_sims[order]
        lo, hi = pool.min(), pool.max()
        span = hi - lo if hi - lo > 1e-9 else 1.0

        candidates = []
        for idx in order:
            frame = frames[idx]
            score = float(line_sims[idx])
            confidence = round(float((score - lo) / span), 3)
            candidates.append({
                "image_id": frame["id"],
                "image": frame["full"],
                "clip_score": round(score, 4),
                "confidence": confidence,
                "relation": classify_relation(line, frame, score),
            })

        results.append({"index": i, "line": line, "candidates": candidates})

    return results
