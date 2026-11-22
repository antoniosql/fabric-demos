#!/usr/bin/env python3
"""Despliegue de la demo «Fabric Semantic Views» desde cero, con la REST API de Fabric.

Crea (o reutiliza) el workspace en tu capacidad, el lakehouse, sube los CSV y el paquete PySpark a OneLake,
publica los notebooks con el lakehouse por defecto asociado y, opcionalmente, los ejecuta.

    python scripts/fabdemo.py check              # config, login y capacidad
    python scripts/fabdemo.py deploy --run       # lo crea todo y ejecuta 00 y 01
    python scripts/fabdemo.py --dry-run deploy   # ensayo: imprime cada llamada sin tocar Fabric
    python scripts/fabdemo.py run 01             # re-ejecuta un notebook (por prefijo de nombre)
    python scripts/fabdemo.py status
    python scripts/fabdemo.py teardown --yes

Toda la configuración sale de `.env` (copia `.env.example`). Autenticación interactiva: no hay secretos.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATE_FILE = ROOT / ".state" / "state.json"

FABRIC = "https://api.fabric.microsoft.com/v1"
FABRIC_SCOPE = "https://api.fabric.microsoft.com/.default"
STORAGE_SCOPE = "https://storage.azure.com/.default"
ONELAKE_DFS = "https://onelake.dfs.fabric.microsoft.com"

# Qué sube `deploy` y dónde (rutas relativas a Files/ del lakehouse).
DATA_DIR = ROOT / "data"
DATA_TARGET = "bronze"
PACKAGE_DIR = ROOT / "src" / "frasohome_fabric"
PACKAGE_TARGET = "src/frasohome_fabric"
NOTEBOOKS_DIR = ROOT / "notebooks"
DEFAULT_RUN = ("00_build_lakehouse", "01_prep_vista_semantica")


# ------------------------------------------------------------------ configuración
def parse_env_file(path: Path) -> dict[str, str]:
    """Lee un fichero .env (KEY=VALUE, comentarios con #, comillas opcionales)."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        values[key.strip()] = value
    return values


@dataclass(frozen=True)
class Config:
    tenant_id: str
    capacity_id: str
    capacity_name: str
    workspace_name: str
    lakehouse_name: str
    lakehouse_schemas: bool
    auth_mode: str


def load_config(env_path: Path | None = None) -> Config:
    """Variables de .env; las del entorno del sistema tienen prioridad."""
    env = {**parse_env_file(env_path or ROOT / ".env"), **os.environ}

    def get(name: str, default: str = "") -> str:
        return env.get(name, default).strip()

    return Config(
        tenant_id=get("FABRIC_TENANT_ID"),
        capacity_id=get("FABRIC_CAPACITY_ID"),
        capacity_name=get("FABRIC_CAPACITY_NAME"),
        workspace_name=get("FABRIC_WORKSPACE_NAME", "ws_frasohome_semantic_views"),
        lakehouse_name=get("FABRIC_LAKEHOUSE_NAME", "lh_frasohome"),
        lakehouse_schemas=get("FABRIC_LAKEHOUSE_SCHEMAS", "true").lower() in ("1", "true", "yes", "si", "sí"),
        auth_mode=get("FABRIC_AUTH_MODE", "cli").lower(),
    )


# ---------------------------------------------------------------------- notebooks
def py_to_ipynb(source: str, lakehouse: dict | None = None) -> dict:
    """Convierte un .py en formato `# %%` / `# %% [markdown]` en un notebook ipynb de Fabric."""
    blocks: list[tuple[str, list[str]]] = []
    for line in source.splitlines():
        if line.startswith("# %%"):
            blocks.append(("markdown" if "[markdown]" in line else "code", []))
        else:
            if not blocks:
                blocks.append(("code", []))
            blocks[-1][1].append(line)

    cells = []
    for kind, lines in blocks:
        if kind == "markdown":
            lines = [ln[2:] if ln.startswith("# ") else ln.lstrip("#") for ln in lines]
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        if not lines:
            continue
        cell: dict[str, Any] = {
            "cell_type": kind,
            "metadata": {},
            "source": [ln + "\n" for ln in lines[:-1]] + [lines[-1]],
        }
        if kind == "code":
            cell.update(execution_count=None, outputs=[])
        cells.append(cell)

    metadata: dict[str, Any] = {
        "language_info": {"name": "python"},
        "kernel_info": {"name": "synapse_pyspark"},
        "kernelspec": {"name": "synapse_pyspark", "display_name": "Synapse PySpark", "language": "Python"},
    }
    if lakehouse:
        metadata["dependencies"] = {"lakehouse": lakehouse}
    return {"nbformat": 4, "nbformat_minor": 5, "metadata": metadata, "cells": cells}


def notebook_files() -> list[Path]:
    return sorted(NOTEBOOKS_DIR.glob("*.py"))


# --------------------------------------------------------------------------- cliente
class FabricError(RuntimeError):
    pass


class Fabric:
    """Cliente mínimo: token por scope, reintento en 429, operaciones largas (LRO) y paginación."""

    def __init__(self, cfg: Config, dry_run: bool = False):
        self.cfg, self.dry_run = cfg, dry_run
        self._cred = None
        self._tokens: dict[str, tuple[str, float]] = {}
        self._session = None

    @property
    def _http(self):
        if self._session is None:
            import requests  # import tardío: --dry-run, --help y los tests no lo necesitan

            self._session = requests.Session()
        return self._session

    # -- auth
    @property
    def credential(self):
        if self._cred is None:
            from azure.identity import AzureCliCredential, DeviceCodeCredential, InteractiveBrowserCredential

            tenant = self.cfg.tenant_id or None
            modes = {"cli": AzureCliCredential, "browser": InteractiveBrowserCredential, "devicecode": DeviceCodeCredential}
            if self.cfg.auth_mode not in modes:
                raise FabricError(f"FABRIC_AUTH_MODE desconocido: {self.cfg.auth_mode} (usa cli, browser o devicecode)")
            self._cred = modes[self.cfg.auth_mode](tenant_id=tenant)
        return self._cred

    def token(self, scope: str = FABRIC_SCOPE) -> str:
        tok, exp = self._tokens.get(scope, ("", 0.0))
        if time.time() < exp - 120:
            return tok
        try:
            t = self.credential.get_token(scope)
        except Exception as e:  # azure-identity lanza varias excepciones según el modo
            raise FabricError(
                f"No se pudo obtener el token ({self.cfg.auth_mode}): {e}\n"
                "Con FABRIC_AUTH_MODE=cli ejecuta antes `az login --tenant <tenant-id>`."
            ) from e
        self._tokens[scope] = (t.token, float(t.expires_on))
        return t.token

    # -- peticiones
    def request(self, method: str, path: str, body: Any = None, *, wait: bool = True) -> Any:
        url = path if path.startswith("http") else f"{FABRIC}{path}"
        print(f"  {method:6s} {url.replace(FABRIC, '')}")
        if self.dry_run:
            return self._fake(method, url, body)
        for _ in range(8):
            r = self._http.request(
                method, url, json=body, headers={"Authorization": f"Bearer {self.token()}"}, timeout=120
            )
            if r.status_code != 429:
                break
            delay = int(r.headers.get("Retry-After", "30"))
            print(f"    429 · reintento en {delay}s")
            time.sleep(delay)
        if r.status_code >= 400:
            raise FabricError(f"{method} {url} -> {r.status_code}: {r.text[:800]}")
        if r.status_code == 202 and "Location" in r.headers:
            if not wait:
                return {"_location": r.headers["Location"]}
            return self._wait(r.headers["Location"], int(r.headers.get("Retry-After", "5")))
        return r.json() if r.content else {}

    def _wait(self, location: str, delay: int) -> Any:
        auth = {"Authorization": f"Bearer {self.token()}"}
        while True:
            time.sleep(min(max(delay, 2), 20))
            p = self._http.get(location, headers=auth, timeout=120)
            if p.status_code == 429:
                delay = int(p.headers.get("Retry-After", "30"))
                continue
            data = p.json() if p.content else {}
            status = (data.get("status") or "").lower()
            if status in ("succeeded", "completed"):
                res = self._http.get(location.rstrip("/") + "/result", headers=auth, timeout=120)
                if res.ok and res.content:
                    try:
                        return res.json()
                    except ValueError:
                        pass
                return data
            if status in ("failed", "cancelled", "deduped"):
                raise FabricError(f"Operación {status}: {json.dumps(data.get('error') or data, ensure_ascii=False)}")
            delay = int(p.headers.get("Retry-After", "5"))

    def paged(self, path: str, key: str = "value") -> list[dict]:
        out, url = [], path
        while url:
            data = self.request("GET", url) or {}
            out += data.get(key) or []
            url = data.get("continuationUri") or ""
            if not url and data.get("continuationToken"):
                url = f"{path}{'&' if '?' in path else '?'}continuationToken={data['continuationToken']}"
        return out

    def _fake(self, method: str, url: str, body: Any) -> Any:
        if method == "GET":
            if url.endswith("/capacities"):
                return {"value": [{"id": "00000000-0000-0000-0000-000000000cap", "displayName": "capacidad-dry-run"}]}
            return {"value": []}
        if method == "POST" and isinstance(body, dict) and "displayName" in body:
            return {"id": str(uuid.uuid4()), "displayName": body["displayName"]}
        if method == "POST" and "/jobs/instances" in url:
            return {"_location": url + "/dry-run"}
        return {}

    # -- OneLake
    def onelake_upload(self, workspace_id: str, lakehouse_id: str, rel_path: str, local: Path) -> None:
        full = f"{lakehouse_id}/Files/{rel_path}"
        print(f"  OneLake {full}  ({local.stat().st_size:,} bytes)")
        if self.dry_run:
            return
        from azure.storage.filedatalake import DataLakeServiceClient

        fs = DataLakeServiceClient(account_url=ONELAKE_DFS, credential=self.credential).get_file_system_client(workspace_id)
        fs.get_file_client(full).upload_data(local.read_bytes(), overwrite=True)


# ------------------------------------------------------------------------ operaciones
def log(msg: str) -> None:
    print(f"• {msg}")


def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def resolve_capacity(fx: Fabric, cfg: Config) -> dict:
    if not (cfg.capacity_id or cfg.capacity_name):
        raise FabricError("Define FABRIC_CAPACITY_ID o FABRIC_CAPACITY_NAME en .env: las vistas semánticas y el Data Agent necesitan capacidad F.")
    caps = fx.paged("/capacities")
    for cap in caps:
        if fx.dry_run or (cfg.capacity_id and cap["id"].lower() == cfg.capacity_id.lower()) or (
            not cfg.capacity_id and cap.get("displayName", "").lower() == cfg.capacity_name.lower()
        ):
            return cap
    visibles = ", ".join(f"{c.get('displayName')} ({c['id']})" for c in caps) or "ninguna"
    raise FabricError(f"No se encontró la capacidad pedida. Capacidades visibles para tu usuario: {visibles}")


def find_workspace(fx: Fabric, name: str) -> dict | None:
    return next((w for w in fx.paged("/workspaces") if w.get("displayName") == name), None)


def find_item(fx: Fabric, ws_id: str, name: str, item_type: str) -> dict | None:
    return next((i for i in fx.paged(f"/workspaces/{ws_id}/items?type={item_type}") if i.get("displayName") == name), None)


def ensure_workspace(fx: Fabric, cfg: Config, capacity_id: str, state: dict) -> str:
    ws = find_workspace(fx, cfg.workspace_name)
    if ws:
        log(f"Workspace '{cfg.workspace_name}' ya existe ({ws['id']}); se reutiliza")
        if (ws.get("capacityId") or "").lower() != capacity_id.lower():
            fx.request("POST", f"/workspaces/{ws['id']}/assignToCapacity", {"capacityId": capacity_id})
            log("  asignado a la capacidad (puede tardar unos segundos en reflejarse)")
            for _ in range(0 if fx.dry_run else 60):
                time.sleep(5)
                if (fx.request("GET", f"/workspaces/{ws['id']}") or {}).get("capacityId", "").lower() == capacity_id.lower():
                    break
        state.update(workspaceId=ws["id"], workspaceCreated=state.get("workspaceCreated", False))
        return ws["id"]
    ws = fx.request("POST", "/workspaces", {
        "displayName": cfg.workspace_name,
        "description": "Demo Fabric Semantic Views: métricas de FraSoHome con Apache Ossie",
        "capacityId": capacity_id,
    })
    log(f"Workspace '{cfg.workspace_name}' creado ({ws['id']})")
    state.update(workspaceId=ws["id"], workspaceCreated=True)
    return ws["id"]


def ensure_lakehouse(fx: Fabric, cfg: Config, ws_id: str) -> str:
    lh = find_item(fx, ws_id, cfg.lakehouse_name, "Lakehouse")
    if lh:
        log(f"Lakehouse '{cfg.lakehouse_name}' ya existe ({lh['id']}); se reutiliza")
        return lh["id"]
    body: dict[str, Any] = {"displayName": cfg.lakehouse_name, "description": "Datos de FraSoHome (bronze, silver y gold)"}
    if cfg.lakehouse_schemas:
        body["creationPayload"] = {"enableSchemas": True}
    lh = fx.request("POST", f"/workspaces/{ws_id}/lakehouses", body)
    log(f"Lakehouse '{cfg.lakehouse_name}' creado ({lh['id']}), con esquemas: {cfg.lakehouse_schemas}")
    return lh["id"]


def upload_files(fx: Fabric, ws_id: str, lh_id: str) -> None:
    csvs = sorted(DATA_DIR.glob("*.csv"))
    if not csvs:
        raise FabricError(f"No hay CSV en {DATA_DIR}")
    log(f"Subiendo {len(csvs)} CSV a Files/{DATA_TARGET}")
    for f in csvs:
        fx.onelake_upload(ws_id, lh_id, f"{DATA_TARGET}/{f.name}", f)
    modules = sorted(PACKAGE_DIR.glob("*.py"))
    log(f"Subiendo el paquete frasohome_fabric ({len(modules)} módulos) a Files/{PACKAGE_TARGET}")
    for f in modules:
        fx.onelake_upload(ws_id, lh_id, f"{PACKAGE_TARGET}/{f.name}", f)


def ensure_notebooks(fx: Fabric, cfg: Config, ws_id: str, lh_id: str) -> dict[str, str]:
    lakehouse = {
        "default_lakehouse": lh_id,
        "default_lakehouse_name": cfg.lakehouse_name,
        "default_lakehouse_workspace_id": ws_id,
    }
    ids: dict[str, str] = {}
    for path in notebook_files():
        name = path.stem
        ipynb = json.dumps(py_to_ipynb(path.read_text(encoding="utf-8"), lakehouse), ensure_ascii=False)
        definition = {"format": "ipynb", "parts": [{
            "path": "notebook-content.ipynb",
            "payload": base64.b64encode(ipynb.encode("utf-8")).decode("ascii"),
            "payloadType": "InlineBase64",
        }]}
        nb = find_item(fx, ws_id, name, "Notebook")
        if nb:
            fx.request("POST", f"/workspaces/{ws_id}/notebooks/{nb['id']}/updateDefinition", {"definition": definition})
            log(f"Notebook '{name}' actualizado ({nb['id']})")
        else:
            nb = fx.request("POST", f"/workspaces/{ws_id}/notebooks", {"displayName": name, "definition": definition})
            log(f"Notebook '{name}' creado ({nb['id']})")
        ids[name] = nb["id"]
    return ids


def run_notebook(fx: Fabric, ws_id: str, nb_id: str, name: str, timeout_s: int = 2400) -> bool:
    log(f"Ejecutando '{name}' (la primera vez arranca Spark: puede tardar unos minutos)")
    res = fx.request("POST", f"/workspaces/{ws_id}/items/{nb_id}/jobs/instances?jobType=RunNotebook", wait=False) or {}
    location = res.get("_location")
    if not location:
        log("  lanzado, pero Fabric no devolvió URL de seguimiento; compruébalo en el portal")
        return True
    if fx.dry_run:
        return True
    started, last = time.time(), ""
    while time.time() - started < timeout_s:
        time.sleep(15)
        job = fx.request("GET", location) or {}
        status = job.get("status", "")
        if status != last:
            print(f"    estado: {status}")
            last = status
        if status == "Completed":
            return True
        if status in ("Failed", "Cancelled", "Deduped"):
            print(json.dumps(job.get("failureReason"), indent=2, ensure_ascii=False))
            return False
    print("    tiempo de espera agotado; el notebook sigue en el portal")
    return False


def portal_url(ws_id: str) -> str:
    return f"https://app.fabric.microsoft.com/groups/{ws_id}"


# --------------------------------------------------------------------------- comandos
def cmd_check(fx: Fabric, cfg: Config, args) -> int:
    print(f"Workspace : {cfg.workspace_name}\nLakehouse : {cfg.lakehouse_name} (esquemas: {cfg.lakehouse_schemas})")
    print(f"Tenant    : {cfg.tenant_id or '(el de tu sesión)'}\nAuth      : {cfg.auth_mode}")
    cap = resolve_capacity(fx, cfg)
    print(f"Capacidad : {cap.get('displayName')} ({cap['id']}) · {cap.get('sku', '?')} · {cap.get('region', '?')}")
    existing = find_workspace(fx, cfg.workspace_name)
    print(f"Workspace existente: {'sí (' + existing['id'] + ')' if existing else 'no, se creará'}")
    missing = [p for p in (DATA_DIR, PACKAGE_DIR, NOTEBOOKS_DIR) if not p.is_dir()]
    if missing:
        raise FabricError(f"Faltan carpetas del repo: {missing}")
    print(f"Repo OK   : {len(list(DATA_DIR.glob('*.csv')))} CSV, {len(list(PACKAGE_DIR.glob('*.py')))} módulos, {len(notebook_files())} notebooks")
    return 0


def cmd_deploy(fx: Fabric, cfg: Config, args) -> int:
    only = set(args.only.split(",")) if args.only else {"platform", "data", "notebooks"}
    unknown = only - {"platform", "data", "notebooks"}
    if unknown:
        raise FabricError(f"--only desconocido: {sorted(unknown)} (usa platform, data, notebooks)")
    state = load_state() if not fx.dry_run else {}
    cap = resolve_capacity(fx, cfg)
    log(f"Capacidad: {cap.get('displayName')} ({cap['id']})")

    ws_id = ensure_workspace(fx, cfg, cap["id"], state)
    lh_id = ensure_lakehouse(fx, cfg, ws_id)
    state.update(workspaceId=ws_id, lakehouseId=lh_id, workspaceName=cfg.workspace_name, lakehouseName=cfg.lakehouse_name)
    if not fx.dry_run:
        save_state(state)
    if "data" in only:
        upload_files(fx, ws_id, lh_id)
    nb_ids = state.get("notebooks", {})
    if "notebooks" in only:
        nb_ids = ensure_notebooks(fx, cfg, ws_id, lh_id)
        state["notebooks"] = nb_ids
        if not fx.dry_run:
            save_state(state)

    if args.run:
        for name in DEFAULT_RUN:
            if name not in nb_ids or not run_notebook(fx, ws_id, nb_ids[name], name):
                print(f"✗ '{name}' no terminó bien; revisa el notebook en el portal.", file=sys.stderr)
                return 1

    print(f"\nListo. Portal: {portal_url(ws_id)}")
    if not args.run:
        print("Siguiente paso: `python scripts/fabdemo.py run` (o ejecuta 00 y 01 desde el portal).")
    else:
        print("Siguiente paso: sigue el guion del README (acto 1: New semantic view en el lakehouse).")
    return 0


def cmd_run(fx: Fabric, cfg: Config, args) -> int:
    state = load_state()
    if not state.get("workspaceId"):
        raise FabricError("No hay estado: ejecuta primero `deploy`.")
    nb_ids = state.get("notebooks", {})
    wanted = args.notebooks or list(DEFAULT_RUN)
    for want in wanted:
        match = [n for n in nb_ids if n.startswith(want)]
        if len(match) != 1:
            raise FabricError(f"'{want}' no identifica un notebook único. Disponibles: {', '.join(sorted(nb_ids))}")
        if not run_notebook(fx, state["workspaceId"], nb_ids[match[0]], match[0]):
            return 1
    return 0


def cmd_status(fx: Fabric, cfg: Config, args) -> int:
    state = load_state()
    if not state.get("workspaceId"):
        print("Sin despliegue registrado (.state/state.json).")
        return 0
    ws_id = state["workspaceId"]
    print(f"Workspace: {state.get('workspaceName')} ({ws_id})\nPortal   : {portal_url(ws_id)}")
    for it in fx.paged(f"/workspaces/{ws_id}/items"):
        print(f"  {it.get('type'):12s} {it.get('displayName')}")
    return 0


def cmd_teardown(fx: Fabric, cfg: Config, args) -> int:
    state = load_state()
    ws_id = state.get("workspaceId")
    if not ws_id:
        print("Nada que borrar: no hay estado en .state/state.json.")
        return 0
    if not args.yes:
        raise FabricError("Esto borra recursos de Fabric. Repite con --yes para confirmar.")
    if state.get("workspaceCreated"):
        log(f"Borrando el workspace '{state.get('workspaceName')}' (lo creó este script)")
        fx.request("DELETE", f"/workspaces/{ws_id}")
    else:
        log("El workspace ya existía antes del despliegue: solo se borran el lakehouse y los notebooks de la demo")
        for it in fx.paged(f"/workspaces/{ws_id}/items"):
            if it["id"] in (state.get("lakehouseId"), *state.get("notebooks", {}).values()):
                fx.request("DELETE", f"/workspaces/{ws_id}/items/{it['id']}")
                log(f"  borrado {it.get('type')} {it.get('displayName')}")
    if not fx.dry_run:
        STATE_FILE.unlink(missing_ok=True)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dry-run", action="store_true", help="imprime las llamadas sin ejecutarlas ni autenticar")
    p.add_argument("--env", type=Path, help="ruta de un .env alternativo")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("check", help="valida config, login y capacidad").set_defaults(fn=cmd_check)
    d = sub.add_parser("deploy", help="crea workspace, lakehouse, datos y notebooks (idempotente)")
    d.add_argument("--run", action="store_true", help="ejecuta 00_build_lakehouse y 01_prep_vista_semantica al terminar")
    d.add_argument("--only", help="subconjunto separado por comas: platform, data, notebooks")
    d.set_defaults(fn=cmd_deploy)
    r = sub.add_parser("run", help="ejecuta notebooks ya desplegados (por defecto 00 y 01)")
    r.add_argument("notebooks", nargs="*", help="prefijos de nombre, p. ej. 01 o 99")
    r.set_defaults(fn=cmd_run)
    sub.add_parser("status", help="muestra el workspace y sus ítems").set_defaults(fn=cmd_status)
    t = sub.add_parser("teardown", help="borra lo desplegado")
    t.add_argument("--yes", action="store_true")
    t.set_defaults(fn=cmd_teardown)
    return p


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):  # evita UnicodeEncodeError al redirigir la salida en Windows
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    cfg = load_config(args.env)
    try:
        return args.fn(Fabric(cfg, dry_run=args.dry_run), cfg, args)
    except FabricError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
