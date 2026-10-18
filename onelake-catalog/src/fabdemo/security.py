"""OneLake security: roles de acceso a datos con RLS y CLS sobre el lakehouse."""
from __future__ import annotations

import json

from .client import FabricClient
from .config import ROOT, Config, State, render
from .fabric import log

ROLES_FILE = ROOT / "security" / "onelake-roles.json"
_KEEP = ("name", "decisionRules", "members")


def _clean(role: dict) -> dict:
    return {k: role[k] for k in _KEEP if k in role}


def apply_roles(c: FabricClient, ws_id: str, lh_id: str, cfg: Config, state: State) -> None:
    desired = json.loads(render(ROLES_FILE.read_text(encoding="utf-8"), cfg, state))["value"]
    current = (c.get(f"/workspaces/{ws_id}/items/{lh_id}/dataAccessRoles") or {}).get("value", [])
    by_name = {r["name"]: _clean(r) for r in current}
    for r in desired:
        by_name[r["name"]] = r
    c.put(f"/workspaces/{ws_id}/items/{lh_id}/dataAccessRoles", {"value": list(by_name.values())})
    log(f"Roles de OneLake security aplicados: {', '.join(r['name'] for r in desired)} "
        f"(conservados: {', '.join(n for n in by_name if n not in {d['name'] for d in desired}) or '—'})")


def show_roles(c: FabricClient, ws_id: str, lh_id: str) -> None:
    roles = (c.get(f"/workspaces/{ws_id}/items/{lh_id}/dataAccessRoles") or {}).get("value", [])
    for r in roles:
        rules = r.get("decisionRules", [])
        paths = [v for rule in rules for p in rule.get("permission", [])
                 if p.get("attributeName") == "Path" for v in p.get("attributeValueIncludedIn", [])]
        cons = [rule.get("constraints") for rule in rules if rule.get("constraints")]
        print(f"  {r['name']}: {', '.join(paths) or '—'}{'  [RLS/CLS]' if cons else ''}")
