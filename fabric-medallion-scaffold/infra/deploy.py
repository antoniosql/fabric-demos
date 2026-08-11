#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Despliega el esqueleto medallon de FraSoHome en Microsoft Fabric.

Crea (idempotente) el dominio, los workspaces por capa, los lakehouses y asigna la capacidad,
segun `config/workspaces.json`. Al terminar, sube config/ingestion + data/ a LH_Landing/Files
(ver `infra/upload_data.py`), publica los notebooks NB_* (ver `infra/publish_notebooks.py`) y los
ejecuta en orden Bronze -> Silver -> Gold via Fabric CLI (ver `infra/run_notebooks.py`), salvo que
se pase `--skip-upload` / `--skip-notebooks` / `--skip-run`. DRY-RUN por defecto; usa `--apply`
para ejecutar de verdad.

Ejecutar notebooks requiere el Fabric CLI aparte: `pip install ms-fabric-cli` + `fab auth login`
(sesion propia del CLI, distinta del login interactivo de este script).

    python infra/deploy.py                 # muestra el plan (no cambia nada)
    python infra/deploy.py --apply         # ejecuta todo (abre login interactivo + fab job run)
    python infra/deploy.py --design collapsed --apply
    python infra/deploy.py --apply --skip-upload --skip-notebooks --skip-run   # solo infraestructura

Variables (.env):  FABRIC_TENANT_ID, FABRIC_CAPACITY_ID
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

from fabric_client import FabricClient
from publish_notebooks import publish_notebooks
from run_notebooks import run_notebooks
from upload_data import upload_landing_data

ROOT = Path(__file__).resolve().parents[1]
GUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


def load_env() -> None:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def main() -> None:
    ap = argparse.ArgumentParser(description="Deploy medallion FraSoHome en Fabric.")
    ap.add_argument("--apply", action="store_true", help="Ejecuta los cambios (por defecto dry-run).")
    ap.add_argument("--design", choices=["separated", "collapsed"], default=None,
                    help="Sobrescribe el diseño seleccionado en workspaces.json.")
    ap.add_argument("--skip-upload", action="store_true",
                    help="No subir config/ingestion + data/ a LH_Landing/Files tras el despliegue.")
    ap.add_argument("--skip-notebooks", action="store_true",
                    help="No publicar los notebooks NB_* tras el despliegue.")
    ap.add_argument("--skip-run", action="store_true",
                    help="No ejecutar los notebooks (fab job run) tras publicarlos.")
    ap.add_argument("--timeout", type=int, default=3600,
                    help="Timeout por notebook al ejecutarlos con fab job run, en segundos (default 3600).")
    args = ap.parse_args()

    load_env()
    cfg = json.loads((ROOT / "config" / "workspaces.json").read_text(encoding="utf-8"))
    design_key = args.design or cfg["design"]["selected"]
    design = cfg["design"]["options"][design_key]
    capacity_id = os.environ.get("FABRIC_CAPACITY_ID", "")
    tenant_id = os.environ.get("FABRIC_TENANT_ID") or None

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"== Deploy medallion FraSoHome · diseño='{design_key}' · modo={mode} ==")
    print(f"   {design['description']}\n")
    if not capacity_id:
        print("   ! FABRIC_CAPACITY_ID vacio en .env — los workspaces se crearan sin capacidad asignada.\n")
    elif not GUID_RE.match(capacity_id):
        raise SystemExit(
            "FABRIC_CAPACITY_ID no es un GUID valido: "
            f"'{capacity_id}'.\n"
            "Debe ser el GUID de la capacidad Fabric (no el resource id de Azure). "
            "Obtenlo con `fab capacity list` o `GET /v1/capacities`."
        )

    client = FabricClient(apply=args.apply, tenant_id=tenant_id)

    # 1) Dominio
    dom = client.ensure_domain(cfg["domain"]["name"], cfg["domain"].get("description", ""))
    domain_id = dom.get("id", "")

    # 2) Workspaces + lakehouses + capacidad
    ws_ids: list[str] = []
    for ws in design["workspaces"]:
        w = client.ensure_workspace(ws["name"], capacity_id or None)
        wid = w.get("id", f"<{ws['name']}>")
        ws_ids.append(wid)
        if capacity_id and args.apply and w.get("id"):
            client.assign_capacity(wid, capacity_id)
        for lh in ws["lakehouses"]:
            client.ensure_lakehouse(wid, lh)

    # 3) Asignar workspaces al dominio
    if domain_id:
        client.assign_workspaces_to_domain(domain_id, [i for i in ws_ids if not i.startswith("<")])

    # 4) Subir config/ingestion + data/ a LH_Landing/Files
    if not args.skip_upload:
        print("\n-- Subiendo config/ingestion + data/ a LH_Landing/Files --")
        upload_landing_data(client, cfg, design_key)

    # 5) Publicar los notebooks NB_* (Bronze -> Silver -> Gold)
    if not args.skip_notebooks:
        print("\n-- Publicando notebooks NB_* --")
        workspace_ids = dict(zip((ws["name"] for ws in design["workspaces"]), ws_ids))
        publish_notebooks(client, cfg, design_key, workspace_ids)

    # 6) Ejecutar los notebooks en orden (fab job run)
    if not args.skip_run:
        print("\n-- Ejecutando notebooks NB_* (fab job run) --")
        run_notebooks(cfg, design_key, args.apply, args.timeout)

    print("\nHecho." if args.apply else "\nPlan mostrado (dry-run). Repite con --apply para ejecutar.")


if __name__ == "__main__":
    main()
