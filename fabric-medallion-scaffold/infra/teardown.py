#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Limpieza: elimina los workspaces creados por el deploy para dejar el entorno como estaba.

DRY-RUN por defecto; `--apply` para ejecutar. No borra la capacidad ni el dominio compartido
salvo que se indique `--delete-domain` (requiere permisos de admin).

    python infra/teardown.py               # muestra que borraria
    python infra/teardown.py --apply       # borra los workspaces de la demo
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from fabric_client import FabricClient
from deploy import load_env

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    ap = argparse.ArgumentParser(description="Teardown medallion FraSoHome.")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--design", choices=["separated", "collapsed"], default=None)
    args = ap.parse_args()

    load_env()
    cfg = json.loads((ROOT / "config" / "workspaces.json").read_text(encoding="utf-8"))
    design_key = args.design or cfg["design"]["selected"]
    design = cfg["design"]["options"][design_key]

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"== Teardown medallion FraSoHome · diseño='{design_key}' · modo={mode} ==\n")
    client = FabricClient(apply=args.apply, tenant_id=os.environ.get("FABRIC_TENANT_ID") or None)

    for ws in design["workspaces"]:
        found = client.find_workspace(ws["name"]) if args.apply else None
        if found:
            client.delete_workspace(found["id"])
        else:
            print(f"   {'[dry-run] borraria' if not args.apply else '= no existe'}: {ws['name']}")

    print("\nHecho." if args.apply else "\nPlan mostrado (dry-run). Repite con --apply para ejecutar.")


if __name__ == "__main__":
    main()
