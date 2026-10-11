"""Sincroniza los CSV de las demos con la fuente de verdad: antoniosql/frasohome-demos.

Cada demo lleva su propia copia de los datos para poder desplegarse sola. Este script
evita que esas copias se separen de la original. Las correspondencias están en
data-sources.json (raíz del repositorio).

Uso:
    python scripts/sync_frasohome_data.py --check                  # compara con GitHub (main)
    python scripts/sync_frasohome_data.py                          # actualiza las copias desde GitHub
    python scripts/sync_frasohome_data.py --source ../frasohome-demos [--check]   # usa un clon local
    python scripts/sync_frasohome_data.py --ref v1.0 --check       # compara con otra rama o etiqueta

La comparación ignora la diferencia CRLF/LF, que depende de la configuración de git de cada equipo.
Solo usa la biblioteca estándar de Python.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data-sources.json"


def normalize(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def read_source(rel_path: str, repo: str, ref: str, local: Path | None) -> bytes:
    if local is not None:
        return (local / rel_path).read_bytes()
    url = f"https://raw.githubusercontent.com/{repo}/{ref}/{rel_path}"
    with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310 - URL fija de GitHub
        return response.read()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="solo compara; termina con código 1 si hay diferencias")
    parser.add_argument("--source", type=Path, help="ruta a un clon local de frasohome-demos")
    parser.add_argument("--ref", help="rama o etiqueta de frasohome-demos (por defecto, la del manifiesto)")
    args = parser.parse_args()

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    repo, ref = manifest["source_repo"], args.ref or manifest["source_ref"]
    origin = args.source.resolve() if args.source else f"{repo}@{ref}"
    print(f"Fuente: {origin}")

    differences, errors = [], []
    for entry in manifest["files"]:
        target = ROOT / entry["target"]
        try:
            source = read_source(entry["source"], repo, ref, args.source)
        except Exception as exc:  # noqa: BLE001 - informamos y seguimos con el resto
            errors.append(f"{entry['source']}: {exc}")
            continue
        current = target.read_bytes() if target.exists() else None
        if current is not None and normalize(current) == normalize(source):
            continue
        differences.append(entry["target"])
        if not args.check:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source)

    total = len(manifest["files"])
    for err in errors:
        print(f"ERROR   {err}")
    for diff in differences:
        print(("DIFIERE " if args.check else "ACTUALIZADO ") + diff)
    print(f"{total} ficheros revisados · {len(differences)} con diferencias · {len(errors)} errores")
    if errors:
        return 2
    if args.check and differences:
        print("Ejecuta `python scripts/sync_frasohome_data.py` para actualizar las copias.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
