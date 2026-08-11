#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ejecuta los notebooks NB_* ya publicados en Fabric, en orden Bronze -> Silver -> Gold,
via Fabric CLI (`fab job run`).

A diferencia de deploy.py / upload_data.py / publish_notebooks.py (que hablan con la Fabric REST
API usando azure-identity), este paso invoca el Fabric CLI (`fab`, dependencia del proyecto via
`ms-fabric-cli`, instalado con `uv sync`) como proceso externo. Requiere:

- `fab auth login` ya hecho (sesion propia del CLI, distinta del login interactivo de los demas
  scripts). Con tenant fijo: `fab auth login --tenant <FABRIC_TENANT_ID>`.
- Los workspaces y los notebooks ya publicados (`infra/deploy.py --apply` o
  `infra/publish_notebooks.py --apply`).

`fab job run <workspace>.Workspace/<notebook>.Notebook` es sincrono (bloquea hasta que el job
Spark termina). Este script para la cadena en el primer notebook que falle (exit code != 0).
DRY-RUN por defecto; usa --apply para ejecutar de verdad.

    python infra/run_notebooks.py                 # muestra los `fab job run` que se lanzarian
    python infra/run_notebooks.py --apply          # ejecuta Bronze -> Silver -> Gold de verdad
    python infra/run_notebooks.py --apply --timeout 1800
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

from publish_notebooks import NOTEBOOKS_BY_LAYER, workspace_for_layer

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TIMEOUT = 3600


def check_fab_available() -> None:
    if not shutil.which("fab"):
        raise SystemExit(
            "No se encontro el ejecutable `fab` en el PATH.\n"
            "Ejecuta `uv sync` (instala ms-fabric-cli) y `fab auth login` antes de --apply."
        )


def run_notebooks(cfg: dict, design_key: str, apply: bool, timeout: int = DEFAULT_TIMEOUT) -> None:
    if apply:
        check_fab_available()

    for layer, filename in NOTEBOOKS_BY_LAYER.items():
        notebook_name = Path(filename).stem
        workspace_name = workspace_for_layer(cfg, design_key, layer)["name"]
        target = f"{workspace_name}.Workspace/{notebook_name}.Notebook"
        cmd = ["fab", "job", "run", target, "--timeout", str(timeout)]

        if not apply:
            print(f"   [dry-run] {' '.join(cmd)}")
            continue

        print(f"   > {' '.join(cmd)}")
        result = subprocess.run(cmd)
        if result.returncode != 0:
            raise SystemExit(f"El notebook {notebook_name} fallo (exit {result.returncode}). Se detiene la cadena.")
        print(f"   = {notebook_name} completado")


def main() -> None:
    ap = argparse.ArgumentParser(description="Ejecuta NB_* en Fabric en orden, via `fab job run`.")
    ap.add_argument("--apply", action="store_true", help="Ejecuta de verdad (por defecto dry-run).")
    ap.add_argument("--design", choices=["separated", "collapsed"], default=None,
                    help="Sobrescribe el diseno seleccionado en workspaces.json.")
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                    help=f"Timeout por notebook, en segundos (default {DEFAULT_TIMEOUT}).")
    args = ap.parse_args()

    cfg = json.loads((ROOT / "config" / "workspaces.json").read_text(encoding="utf-8"))
    design_key = args.design or cfg["design"]["selected"]

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"== Ejecutar notebooks FraSoHome · diseno='{design_key}' · modo={mode} ==\n")

    run_notebooks(cfg, design_key, args.apply, args.timeout)

    print("\nHecho." if args.apply else "\nPlan mostrado (dry-run). Repite con --apply para ejecutar.")


if __name__ == "__main__":
    main()
