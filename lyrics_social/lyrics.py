"""Carga de letras: un archivo de texto plano, una frase por linea."""
from pathlib import Path


def load_lines(path):
    text = Path(path).read_text(encoding="utf-8")
    return [line.strip() for line in text.splitlines() if line.strip()]
