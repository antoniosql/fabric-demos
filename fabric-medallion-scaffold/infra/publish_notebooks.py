#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Publica los notebooks locales (src/notebooks/NB_*.py) como items Notebook en Fabric.

Cada notebook se sube al workspace que le corresponde segun la capa (`layer`) en
config/workspaces.json: Bronze -> capa "bronze" (o "all" en el diseno collapsed), Silver -> "silver",
Gold -> "gold". El .py se envuelve en un .ipynb de una sola celda (formato `ipynb`, soportado por la
Fabric REST API sin marcadores especiales de celda tipo `# META`/`# CELL`).

Idempotente: si el notebook ya existe (por displayName), se actualiza su definicion en vez de
duplicarlo. DRY-RUN por defecto; usa --apply para publicar de verdad. Requiere que los workspaces
ya existan (`infra/deploy.py --apply`); `infra/deploy.py --apply` lo invoca automaticamente al final.

    python infra/publish_notebooks.py                 # muestra que se publicaria
    python infra/publish_notebooks.py --apply          # publica de verdad (login interactivo)

Variables (.env): FABRIC_TENANT_ID
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from fabric_client import FabricClient

ROOT = Path(__file__).resolve().parents[1]

NOTEBOOKS_BY_LAYER = {
    "bronze": "NB_Load_Bronze_Retail.py",
    "silver": "NB_Transform_Bronze_To_Silver.py",
    "gold": "NB_Build_Gold_Star.py",
}


def load_env() -> None:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def workspace_for_layer(cfg: dict, design_key: str, layer: str) -> dict:
    design = cfg["design"]["options"][design_key]
    for ws in design["workspaces"]:
        if ws["layer"] in (layer, "all"):
            return ws
    raise SystemExit(f"Ningun workspace del diseno '{design_key}' cubre la capa '{layer}'.")


def publish_notebooks(client: FabricClient, cfg: dict, design_key: str, workspace_ids: dict[str, str]) -> None:
    """workspace_ids: nombre de workspace -> id real (vacio en dry-run, usa placeholder `<nombre>`)."""
    for layer, filename in NOTEBOOKS_BY_LAYER.items():
        ws = workspace_for_layer(cfg, design_key, layer)
        local_path = ROOT / "src" / "notebooks" / filename
        if not local_path.exists():
            raise SystemExit(f"No existe {local_path}")
        workspace_id = workspace_ids.get(ws["name"], f"<{ws['name']}>")
        client.ensure_notebook(workspace_id, local_path.stem, local_path)


def main() -> None:
    ap = argparse.ArgumentParser(description="Publica NB_* como notebooks de Fabric.")
    ap.add_argument("--apply", action="store_true", help="Publica de verdad (por defecto dry-run).")
    ap.add_argument("--design", choices=["separated", "collapsed"], default=None,
                    help="Sobrescribe el diseno seleccionado en workspaces.json.")
    args = ap.parse_args()

    load_env()
    cfg = json.loads((ROOT / "config" / "workspaces.json").read_text(encoding="utf-8"))
    design_key = args.design or cfg["design"]["selected"]
    tenant_id = os.environ.get("FABRIC_TENANT_ID") or None

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"== Publicar notebooks FraSoHome · diseno='{design_key}' · modo={mode} ==\n")

    client = FabricClient(apply=args.apply, tenant_id=tenant_id)

    workspace_ids: dict[str, str] = {}
    if args.apply:
        for ws in cfg["design"]["options"][design_key]["workspaces"]:
            found = client.find_workspace(ws["name"])
            if not found or not found.get("id"):
                raise SystemExit(f"El workspace '{ws['name']}' no existe. Ejecuta primero infra/deploy.py --apply.")
            workspace_ids[ws["name"]] = found["id"]

    publish_notebooks(client, cfg, design_key, workspace_ids)

    print("\nHecho." if args.apply else "\nPlan mostrado (dry-run). Repite con --apply para publicar de verdad.")
    print("Siguiente paso: ejecutar los notebooks (portal de Fabric o `fab notebook run`).")


if __name__ == "__main__":
    main()
