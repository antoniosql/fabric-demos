"""Valida que todos los .ipynb del repositorio son JSON y notebooks nbformat válidos.

No ejecuta los notebooks (necesitarían un Lakehouse de Fabric): solo detecta ficheros
corruptos o mal guardados antes de una sesión.
"""
from __future__ import annotations

import sys
from pathlib import Path

import nbformat

ROOT = Path(__file__).resolve().parents[2]
SKIP = {".git", "node_modules", ".venv"}


def main() -> int:
    notebooks = [p for p in ROOT.rglob("*.ipynb") if not SKIP.intersection(p.parts)]
    failed = 0
    for path in sorted(notebooks):
        rel = path.relative_to(ROOT).as_posix()
        try:
            nb = nbformat.read(path, as_version=4)
            nbformat.validate(nb)
            print(f"OK  {rel}")
        except Exception as exc:  # noqa: BLE001 - queremos informar de cualquier fallo
            failed += 1
            print(f"::error file={rel}::{exc}")
    print(f"{len(notebooks)} notebooks revisados, {failed} con errores.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
