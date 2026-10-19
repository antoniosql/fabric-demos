"""Operaciones idempotentes sobre Fabric (workspaces, dominios, tags, ítems, etiquetas)."""
from __future__ import annotations

import base64
import json

from .client import FabricApiError, FabricClient


def b64(data: str | bytes) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return base64.b64encode(data).decode("ascii")


def log(msg: str) -> None:
    print(f"• {msg}")


# ------------------------------------------------------------------ capacity
def get_capacity(c: FabricClient, capacity_id: str) -> dict | None:
    for cap in c.paged("/capacities"):
        if cap.get("id", "").lower() == capacity_id.lower() or c.dry_run:
            return cap
    return None


# ---------------------------------------------------------------- workspaces
def find_workspace(c: FabricClient, name: str) -> dict | None:
    for ws in c.paged("/workspaces"):
        if ws.get("displayName") == name:
            return ws
    return None


def ensure_workspace(c: FabricClient, name: str, capacity_id: str, description: str = "") -> str:
    ws = find_workspace(c, name)
    if ws:
        log(f"Workspace '{name}' ya existe ({ws['id']})")
        if ws.get("capacityId", "").lower() != capacity_id.lower():
            c.post(f"/workspaces/{ws['id']}/assignToCapacity", {"capacityId": capacity_id})
            log(f"  asignado a la capacidad {capacity_id}")
        return ws["id"]
    ws = c.post("/workspaces", {"displayName": name, "description": description, "capacityId": capacity_id})
    log(f"Workspace '{name}' creado ({ws['id']})")
    return ws["id"]


def ensure_role(c: FabricClient, ws_id: str, principal_id: str, principal_type: str, role: str) -> None:
    try:
        c.post(f"/workspaces/{ws_id}/roleAssignments",
               {"principal": {"id": principal_id, "type": principal_type}, "role": role})
        log(f"  rol {role} → {principal_type} {principal_id[:8]}…")
    except FabricApiError as e:
        if e.status == 409 or "Already" in e.code:
            log(f"  rol de {principal_type} {principal_id[:8]}… ya asignado")
        else:
            raise


def delete_workspace(c: FabricClient, ws_id: str) -> None:
    c.delete(f"/workspaces/{ws_id}")


# ------------------------------------------------------------------- domains
def find_domain(c: FabricClient, name: str) -> dict | None:
    data = c.get("/admin/domains") or {}
    for d in data.get("domains", data.get("value", [])):
        if d.get("displayName") == name:
            return d
    return None


def ensure_domain(c: FabricClient, name: str, description: str) -> str:
    d = find_domain(c, name)
    if d:
        log(f"Dominio '{name}' ya existe ({d['id']})")
        return d["id"]
    d = c.post("/admin/domains", {"displayName": name[:40], "description": description[:256]})
    log(f"Dominio '{name}' creado ({d['id']})")
    return d["id"]


def assign_domain_workspaces(c: FabricClient, domain_id: str, ws_ids: list[str]) -> None:
    c.post(f"/admin/domains/{domain_id}/assignWorkspaces", {"workspacesIds": ws_ids})
    log(f"{len(ws_ids)} workspaces asignados al dominio")


def assign_domain_admins(c: FabricClient, domain_id: str, user_ids: list[str]) -> None:
    if not user_ids:
        return
    try:
        c.post(f"/admin/domains/{domain_id}/roleAssignments/bulkAssign",
               {"type": "Admins", "principals": [{"id": u, "type": "User"} for u in user_ids]})
        log(f"{len(user_ids)} administradores de dominio asignados")
    except FabricApiError as e:
        if "AlreadyExists" in e.code:
            log("Administradores de dominio ya asignados")
        else:
            raise


def delete_domain(c: FabricClient, domain_id: str) -> None:
    c.delete(f"/admin/domains/{domain_id}")


# ---------------------------------------------------------------------- tags
def list_tags(c: FabricClient) -> list[dict]:
    return list(c.paged("/admin/tags"))


def ensure_domain_tags(c: FabricClient, domain_id: str, names: list[str]) -> dict[str, str]:
    existing = {t["displayName"]: t["id"] for t in list_tags(c)}
    missing = [n for n in names if n not in existing]
    if missing:
        res = c.post("/admin/tags/bulkCreateTags", {
            "scope": {"type": "Domain", "domainId": domain_id},
            "createTagsRequest": [{"displayName": n} for n in missing],
        }) or {}
        for t in res.get("tags", []):
            existing[t["displayName"]] = t["id"]
        log(f"Tags creados: {', '.join(missing)}")
    else:
        log("Tags ya existen")
    return {n: existing[n] for n in names if n in existing}


def apply_tags(c: FabricClient, ws_id: str, item_id: str, tag_ids: list[str]) -> None:
    if tag_ids:
        c.post(f"/workspaces/{ws_id}/items/{item_id}/applyTags", {"tags": tag_ids})


def delete_tag(c: FabricClient, tag_id: str) -> None:
    c.delete(f"/admin/tags/{tag_id}")


# --------------------------------------------------------------------- items
def list_items(c: FabricClient, ws_id: str, item_type: str | None = None) -> list[dict]:
    q = f"?type={item_type}" if item_type else ""
    return list(c.paged(f"/workspaces/{ws_id}/items{q}"))


def find_item(c: FabricClient, ws_id: str, name: str, item_type: str) -> dict | None:
    for it in list_items(c, ws_id, item_type):
        if it.get("displayName") == name:
            return it
    return None


def create_item(c: FabricClient, ws_id: str, name: str, item_type: str,
                description: str = "", definition: dict | None = None) -> dict:
    body = {"displayName": name, "type": item_type}
    if description:
        body["description"] = description
    if definition:
        body["definition"] = definition
    return c.post(f"/workspaces/{ws_id}/items", body)


def ensure_lakehouse(c: FabricClient, ws_id: str, name: str, description: str) -> str:
    it = find_item(c, ws_id, name, "Lakehouse")
    if it:
        log(f"Lakehouse '{name}' ya existe ({it['id']})")
        return it["id"]
    # Sin esquemas: la API Load Table trabaja con /Tables/<tabla>
    body = {"displayName": name}
    if description:
        body["description"] = description
    lh = c.post(f"/workspaces/{ws_id}/lakehouses", body)
    log(f"Lakehouse '{name}' creado ({lh['id']})")
    return lh["id"]


def ensure_notebook(c: FabricClient, ws_id: str, name: str, ipynb: str, description: str) -> str:
    definition = {"format": "ipynb", "parts": [
        {"path": "notebook-content.ipynb", "payload": b64(ipynb), "payloadType": "InlineBase64"}]}
    it = find_item(c, ws_id, name, "Notebook")
    if it:
        c.post(f"/workspaces/{ws_id}/items/{it['id']}/updateDefinition", {"definition": definition})
        log(f"Notebook '{name}' actualizado ({it['id']})")
        return it["id"]
    nb = create_item(c, ws_id, name, "Notebook", description, definition)
    log(f"Notebook '{name}' creado ({nb['id']})")
    return nb["id"]


def set_description(c: FabricClient, ws_id: str, item_id: str, description: str) -> None:
    c.patch(f"/workspaces/{ws_id}/items/{item_id}", {"description": description})


def delete_item(c: FabricClient, ws_id: str, item_id: str) -> None:
    c.delete(f"/workspaces/{ws_id}/items/{item_id}")


# -------------------------------------------------------------------- labels
def set_labels(c: FabricClient, items: list[dict], label_id: str) -> None:
    """items: [{"id":..., "type":...}]. Solo funciona con identidad de usuario (Fabric admin).

    No se envía assignmentMethod: el enum documentado ("Priviledged") no coincide con lo que
    acepta el servicio y provoca 400 InvalidInput. Se usa el valor por defecto (Standard).
    """
    import re
    if not re.fullmatch(r"[0-9a-fA-F-]{36}", label_id or "") or set(label_id.replace("-", "")) == {"0"}:
        raise SystemExit(f"labelId no válido: '{label_id}'. Revisa [labels] en config.toml "
                         "(GUID de Get-Label | Select DisplayName, ImmutableId).")
    res = c.post("/admin/items/bulkSetLabels", {"items": items, "labelId": label_id}) or {}
    for st in res.get("itemsChangeLabelStatus", []):
        mark = "✓" if st.get("status") == "Succeeded" else "✗"
        log(f"  {mark} etiqueta en {st.get('type')} {st.get('id', '')[:8]}… → {st.get('status')}")


def remove_labels(c: FabricClient, items: list[dict]) -> None:
    c.post("/admin/items/bulkRemoveLabels", {"items": items})


# ----------------------------------------------------------------- jobs
def run_notebook(c: FabricClient, ws_id: str, nb_id: str, timeout_s: int = 1800) -> str:
    import time
    res = c.post(f"/workspaces/{ws_id}/items/{nb_id}/jobs/instances?jobType=RunNotebook", wait=False) or {}
    location = (res.get("_headers") or {}).get("Location")
    if not location:
        return "Submitted"
    if c.dry_run:
        return "Completed"
    start = time.time()
    while time.time() - start < timeout_s:
        time.sleep(15)
        job = c.get(location) or {}
        status = job.get("status", "")
        print(f"    notebook: {status}")
        if status in ("Completed", "Failed", "Cancelled", "Deduped"):
            if status == "Failed":
                print(json.dumps(job.get("failureReason"), indent=2, ensure_ascii=False))
            return status
    return "Timeout"
