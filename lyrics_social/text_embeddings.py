"""Embeddings de texto con OpenCLIP, mismo modelo/familia que selector-fotogramas
usa para las imagenes, para que ambos vectores vivan en el mismo espacio."""
import numpy as np


def resolve_device(requested):
    import torch

    if requested != "auto":
        return requested
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def compute_text_embeddings(lines, model_name, pretrained, device):
    import torch
    import open_clip

    model, _, _ = open_clip.create_model_and_transforms(model_name, pretrained=pretrained)
    tokenizer = open_clip.get_tokenizer(model_name)
    model.eval().to(device)

    with torch.no_grad():
        tokens = tokenizer(lines).to(device)
        emb = model.encode_text(tokens)
        emb = emb / emb.norm(dim=-1, keepdim=True)

    return emb.cpu().numpy().astype(np.float32)
