"""Fabric Policies (preview) como código: policy set = ítem PolicySet con definición policySet.json."""
from __future__ import annotations

import base64
import difflib
import json
from pathlib import Path

from .client import FabricApiError, FabricClient
from .config import ROOT, Config, State, render
from .fabric import b64, find_item, log

POLICY_DIR = ROOT / "policies"


def load_policy(path: Path, cfg: Config, state: State) -> dict:
    return json.loads(render(path.read_text(encoding="utf-8"), cfg, state))


def resolve_policy_file(name: str) -> Path:
    p = Path(name)
    if not p.exists():
        p = POLICY_DIR / name
    if not p.exists():
        matches = sorted(POLICY_DIR.glob(f"*{name}*.json"))
        if len(matches) == 1:
            p = matches[0]
    if not p.exists():
        raise SystemExit(f"No encuentro la definición '{name}' en {POLICY_DIR}")
    return p


def _definition(policy: dict) -> dict:
    return {"format": "Beta", "parts": [
        {"path": "policySet.json", "payload": b64(json.dumps(policy, ensure_ascii=False)), "payloadType": "InlineBase64"}]}


def deploy_policy_set(c: FabricClient, ws_id: str, name: str, policy: dict, description: str = "") -> str:
    """Crea el policy set o actualiza su definición. No lo activa."""
    existing = find_item(c, ws_id, name, "PolicySet")
    if existing:
        c.post(f"/workspaces/{ws_id}/items/{existing['id']}/updateDefinition", {"definition": _definition(policy)})
        log(f"Policy set '{name}' actualizado ({existing['id']})")
        return existing["id"]
    ps = c.post(f"/workspaces/{ws_id}/policySets",
                {"displayName": name, "description": description[:256], "definition": _definition(policy)})
    log(f"Policy set '{name}' creado ({ps['id']})")
    return ps["id"]


def get_deployed(c: FabricClient, ws_id: str, ps_id: str) -> dict:
    res = c.post(f"/workspaces/{ws_id}/items/{ps_id}/getDefinition?format=Beta") or {}
    for part in (res.get("definition") or {}).get("parts", []):
        if part.get("path") == "policySet.json":
            return json.loads(base64.b64decode(part["payload"]).decode("utf-8"))
    return {}


def diff(local: dict, remote: dict) -> str:
    a = json.dumps(remote, indent=2, sort_keys=True, ensure_ascii=False).splitlines()
    b = json.dumps(local, indent=2, sort_keys=True, ensure_ascii=False).splitlines()
    return "\n".join(difflib.unified_diff(a, b, "desplegado", "repositorio", lineterm=""))


def activate(c: FabricClient, ws_id: str, ps_id: str, capacity_id: str) -> None:
    c.post(f"/workspaces/{ws_id}/policySets/{ps_id}/activate?allowReplace=true",
           {"scopeType": "Capacity", "capacityId": capacity_id})
    log("Policy set ACTIVADO en la capacidad (efecto en ≤ 15 min)")


def deactivate(c: FabricClient, ws_id: str, ps_id: str) -> None:
    try:
        c.post(f"/workspaces/{ws_id}/policySets/{ps_id}/deactivate", {"scopeType": "Capacity"})
        log("Policy set desactivado")
    except FabricApiError as e:
        if "NotActive" in e.code:
            log("El policy set no estaba activo")
        else:
            raise


def active_for_capacity(c: FabricClient, capacity_id: str) -> dict | None:
    try:
        act = c.get(f"/capacities/{capacity_id}/policySets/active")
        return act if act and act.get("id") else None
    except FabricApiError as e:
        if e.status == 404:
            return None
        raise
