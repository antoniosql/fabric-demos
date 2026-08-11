#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sube config/ingestion/*.json y los CSV de data/ a LH_Landing/Files en Microsoft Fabric (OneLake).

Cada JSON de config/ingestion/ define `source_file` (CSV local) y `landing_path` (destino dentro
de Files/). Este script sube el propio JSON a Files/config/ingestion/ y el CSV a su landing_path,
en LH_Landing del workspace que lo contiene segun config/workspaces.json.

DRY-RUN por defecto; usa --apply para subir de verdad. `infra/deploy.py --apply` lo invoca
automaticamente tras crear los workspaces y lakehouses (usa --skip-upload para omitirlo).

    python infra/upload_data.py                 # muestra que se subiria (no toca nada)
    python infra/upload_data.py --apply          # sube de verdad (login interactivo)
    python infra/upload_data.py --design collapsed --apply

Variables (.env): FABRIC_TENANT_ID
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from fabric_client import FabricClient

ROOT = Path(__file__).resolve().parents[1]


def load_env() -> None:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def landing_workspace_name(cfg: dict, design_key: str) -> str:
    design = cfg["design"]["options"][design_key]
    for ws in design["workspaces"]:
        if "LH_Landing" in ws["lakehouses"]:
            return ws["name"]
    raise SystemExit(f"Ningun workspace del diseno '{design_key}' contiene LH_Landing.")


def upload_landing_data(client: FabricClient, cfg: dict, design_key: str) -> None:
    """Sube config/ingestion/*.json y sus CSV asociados a LH_Landing/Files."""
    workspace_name = landing_workspace_name(cfg, design_key)
    ingestion_files = sorted((ROOT / "config" / "ingestion").glob("*.json"))
    if not ingestion_files:
        raise SystemExit("No hay configs en config/ingestion/.")

    for ing_path in ingestion_files:
        ing = json.loads(ing_path.read_text(encoding="utf-8"))
        client.upload_file(workspace_name, "LH_Landing", f"Files/config/ingestion/{ing_path.name}", ing_path)

        source_file = ROOT / ing["source_file"]
        if not source_file.exists():
            raise SystemExit(f"source_file no existe: {source_file} (definido en {ing_path.name})")
        remote_data = ing["landing_path"].rstrip("/") + "/" + source_file.name
        client.upload_file(workspace_name, "LH_Landing", remote_data, source_file)


def main() -> None:
    ap = argparse.ArgumentParser(description="Sube config/ingestion + data a LH_Landing/Files.")
    ap.add_argument("--apply", action="store_true", help="Sube de verdad (por defecto dry-run).")
    ap.add_argument("--design", choices=["separated", "collapsed"], default=None,
                    help="Sobrescribe el diseno seleccionado en workspaces.json.")
    args = ap.parse_args()

    load_env()
    cfg = json.loads((ROOT / "config" / "workspaces.json").read_text(encoding="utf-8"))
    design_key = args.design or cfg["design"]["selected"]
    tenant_id = os.environ.get("FABRIC_TENANT_ID") or None

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"== Subir datos FraSoHome a LH_Landing · diseno='{design_key}' · modo={mode} ==\n")

    client = FabricClient(apply=args.apply, tenant_id=tenant_id)
    upload_landing_data(client, cfg, design_key)

    print("\nHecho." if args.apply else "\nPlan mostrado (dry-run). Repite con --apply para subir de verdad.")
    print("Siguiente paso: ejecutar los notebooks NB_* (Bronze -> Silver -> Gold).")


if __name__ == "__main__":
    main()
