#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cliente minimo de la Fabric REST API con autenticacion INTERACTIVA.

- Auth: azure-identity InteractiveBrowserCredential (nunca desatendido, sin secretos en el repo).
- Operaciones idempotentes: `ensure_*` busca-o-crea, de modo que reejecutar el deploy no duplica.
- Todas las escrituras respetan un flag `apply`; con `apply=False` solo se registra la accion (dry-run).

Docs: https://learn.microsoft.com/rest/api/fabric/
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import requests

FABRIC_BASE = "https://api.fabric.microsoft.com/v1"
SCOPE = "https://api.fabric.microsoft.com/.default"

ONELAKE_DFS = "https://onelake.dfs.fabric.microsoft.com"
ONELAKE_SCOPE = "https://storage.azure.com/.default"
ONELAKE_API_VERSION = "2023-11-03"


def _onelake_url(workspace_name: str, lakehouse_name: str, path: str) -> str:
    ws = quote(workspace_name.strip("/"), safe="")
    lh = quote(f"{lakehouse_name.strip('/')}.Lakehouse", safe="")
    p = quote(path.strip("/"), safe="/")
    return f"{ONELAKE_DFS}/{ws}/{lh}/{p}"


class FabricClient:
    def __init__(self, apply: bool = False, tenant_id: Optional[str] = None):
        self.apply = apply
        self._token = None
        self._onelake_token = None
        self._tenant_id = tenant_id

    # ----------------------------------------------------------------- auth
    def _get_token(self, scope: str = SCOPE) -> str:
        from azure.identity import InteractiveBrowserCredential
        cred = InteractiveBrowserCredential(tenant_id=self._tenant_id)
        return cred.get_token(scope).token

    def _headers(self) -> dict:
        if not self._token:
            self._token = self._get_token(SCOPE)
        return {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}

    def _onelake_headers(self) -> dict:
        if not self._onelake_token:
            self._onelake_token = self._get_token(ONELAKE_SCOPE)
        return {"Authorization": f"Bearer {self._onelake_token}", "x-ms-version": ONELAKE_API_VERSION}

    # ----------------------------------------------------------------- http
    def _get(self, path: str) -> dict:
        if not self.apply:                      # dry-run: sin red ni login
            return {"value": [], "domains": []}
        r = requests.get(f"{FABRIC_BASE}{path}", headers=self._headers(), timeout=60)
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, body: dict) -> dict:
        if not self.apply:
            print(f"   [dry-run] POST {path}  {body}")
            return {}
        r = requests.post(f"{FABRIC_BASE}{path}", headers=self._headers(), json=body, timeout=120)
        if r.status_code == 202:                      # operacion asincrona (LRO)
            return self._wait_lro(r)
        r.raise_for_status()
        return r.json() if r.text else {}

    def _delete(self, path: str) -> None:
        if not self.apply:
            print(f"   [dry-run] DELETE {path}")
            return
        r = requests.delete(f"{FABRIC_BASE}{path}", headers=self._headers(), timeout=120)
        r.raise_for_status()

    def _wait_lro(self, resp: requests.Response) -> dict:
        url = resp.headers.get("Location")
        while url:
            time.sleep(float(resp.headers.get("Retry-After", 3)))
            r = requests.get(url, headers=self._headers(), timeout=60)
            if r.status_code == 200:
                return r.json() if r.text else {}
            resp = r
        return {}

    # ----------------------------------------------------------- workspaces
    def find_workspace(self, name: str) -> Optional[dict]:
        for w in self._get("/workspaces").get("value", []):
            if w.get("displayName") == name:
                return w
        return None

    def ensure_workspace(self, name: str, capacity_id: Optional[str]) -> dict:
        existing = self.find_workspace(name)
        if existing:
            print(f"   = workspace ya existe: {name}")
            return existing
        print(f"   + creando workspace: {name}")
        body = {"displayName": name}
        if capacity_id:
            body["capacityId"] = capacity_id
        return self._post("/workspaces", body) or {"displayName": name}

    def assign_capacity(self, workspace_id: str, capacity_id: str) -> None:
        print(f"   + asignando capacidad a workspace {workspace_id}")
        self._post(f"/workspaces/{workspace_id}/assignToCapacity", {"capacityId": capacity_id})

    def delete_workspace(self, workspace_id: str) -> None:
        print(f"   - borrando workspace {workspace_id}")
        self._delete(f"/workspaces/{workspace_id}")

    # ------------------------------------------------------------ lakehouses
    def ensure_lakehouse(self, workspace_id: str, name: str) -> dict:
        if self.apply and workspace_id:
            for it in self._get(f"/workspaces/{workspace_id}/lakehouses").get("value", []):
                if it.get("displayName") == name:
                    print(f"   = lakehouse ya existe: {name}")
                    return it
        print(f"   + creando lakehouse: {name}")
        return self._post(f"/workspaces/{workspace_id}/lakehouses", {"displayName": name}) or {"displayName": name}

    # ---------------------------------------------------------------- domains
    def ensure_domain(self, name: str, description: str = "") -> dict:
        # /admin/domains requiere permisos de administrador de Fabric
        try:
            for d in self._get("/admin/domains").get("domains", []):
                if d.get("displayName") == name:
                    print(f"   = dominio ya existe: {name}")
                    return d
        except Exception:
            print("   ! sin permisos de admin para dominios (se omite; crear a mano si aplica)")
            return {}
        print(f"   + creando dominio: {name}")
        return self._post("/admin/domains", {"displayName": name, "description": description}) or {}

    def assign_workspaces_to_domain(self, domain_id: str, workspace_ids: list[str]) -> None:
        if not domain_id:
            return
        print(f"   + asignando {len(workspace_ids)} workspaces al dominio {domain_id}")
        self._post(f"/admin/domains/{domain_id}/assignWorkspaces", {"workspacesIds": workspace_ids})

    # -------------------------------------------------------------- onelake
    def upload_file(self, workspace_name: str, lakehouse_name: str, remote_path: str, local_path: Path) -> None:
        """Sube `local_path` a `remote_path` (p.ej. 'Files/landing/...') via OneLake DFS API."""
        if not self.apply:
            print(f"   [dry-run] PUT onelake://{workspace_name}/{lakehouse_name}.Lakehouse/{remote_path}  ({local_path})")
            return
        headers = self._onelake_headers()
        self._ensure_onelake_directories(workspace_name, lakehouse_name, Path(remote_path).parent.as_posix(), headers)

        url = _onelake_url(workspace_name, lakehouse_name, remote_path)
        r = requests.put(url, headers=headers, params={"resource": "file"}, timeout=120)
        if r.status_code not in (200, 201):
            raise RuntimeError(f"No se pudo crear {remote_path}: {r.status_code} {r.text}")

        data = local_path.read_bytes()
        r = requests.patch(url, headers=headers, params={"action": "append", "position": "0"}, data=data, timeout=300)
        if r.status_code not in (200, 202):
            raise RuntimeError(f"No se pudo escribir {remote_path}: {r.status_code} {r.text}")

        r = requests.patch(url, headers=headers, params={"action": "flush", "position": str(len(data))}, timeout=120)
        if r.status_code not in (200, 201):
            raise RuntimeError(f"No se pudo cerrar {remote_path}: {r.status_code} {r.text}")

        print(f"   + subido: {remote_path}  ({len(data)} bytes)")

    def _ensure_onelake_directories(
        self, workspace_name: str, lakehouse_name: str, directory_path: str, headers: dict
    ) -> None:
        if not directory_path or directory_path == ".":
            return
        parts: list[str] = []
        for part in directory_path.split("/"):
            if not part:
                continue
            parts.append(part)
            path = "/".join(parts)
            r = requests.put(_onelake_url(workspace_name, lakehouse_name, path), headers=headers,
                              params={"resource": "directory"}, timeout=120)
            if r.status_code not in (200, 201, 409):
                raise RuntimeError(f"No se pudo crear directorio {path}: {r.status_code} {r.text}")
