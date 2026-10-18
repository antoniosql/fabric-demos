"""Cliente mínimo para la REST API de Fabric: autenticación, reintentos 429, LRO y paginación.

Modo --dry-run: no llama a la API; imprime cada petición y devuelve respuestas sintéticas
para poder ensayar el flujo completo sin tenant.
"""
from __future__ import annotations

import json
import time
import uuid
from typing import Any, Iterator

import requests

from .auth import FABRIC_SCOPE, POWERBI_SCOPE

FABRIC = "https://api.fabric.microsoft.com/v1"
POWERBI = "https://api.powerbi.com/v1.0/myorg"


class FabricApiError(RuntimeError):
    def __init__(self, status: int, method: str, url: str, payload: Any):
        self.status = status
        self.payload = payload if isinstance(payload, dict) else {"message": str(payload)}
        self.code = self.payload.get("errorCode") or self.payload.get("error", {}).get("code", "")
        msg = self.payload.get("message") or self.payload.get("error", {}).get("message", "")
        super().__init__(f"{method} {url} -> {status} {self.code}: {msg}")


class FabricClient:
    def __init__(self, credential, dry_run: bool = False, verbose: bool = False, label: str = "admin"):
        self.credential = credential
        self.dry_run = dry_run
        self.verbose = verbose or dry_run
        self.label = label
        self.session = requests.Session()
        self._tokens: dict[str, tuple[str, float]] = {}

    # ------------------------------------------------------------------ auth
    def _token(self, scope: str) -> str:
        tok, exp = self._tokens.get(scope, ("", 0))
        if time.time() < exp - 120:
            return tok
        t = self.credential.get_token(scope)
        self._tokens[scope] = (t.token, t.expires_on)
        return t.token

    # --------------------------------------------------------------- request
    def request(self, method: str, path: str, body: Any = None, *, base: str = FABRIC,
                scope: str = FABRIC_SCOPE, params: dict | None = None, wait: bool = True,
                ok_codes: tuple[int, ...] = ()) -> Any:
        url = path if path.startswith("http") else f"{base}{path}"
        if self.verbose:
            shown = "" if body is None else " " + json.dumps(body, ensure_ascii=False)[:300]
            print(f"  [{self.label}] {method} {url.replace(FABRIC, '')}{shown}")
        if self.dry_run:
            return self._fake(method, url, body)

        for attempt in range(8):
            r = self.session.request(
                method, url, params=params, json=body,
                headers={"Authorization": f"Bearer {self._token(scope)}"},
                timeout=120,
            )
            if r.status_code == 429:
                delay = int(r.headers.get("Retry-After", "30"))
                print(f"    429 · reintento en {delay}s")
                time.sleep(delay)
                continue
            break

        if r.status_code in ok_codes:
            return None
        if r.status_code == 202 and wait and r.headers.get("Location"):
            return self._wait_lro(r, scope)
        if r.status_code >= 400:
            try:
                payload = r.json()
            except ValueError:
                payload = r.text
            raise FabricApiError(r.status_code, method, url, payload)
        if not r.content:
            return {"_headers": dict(r.headers)} if r.status_code == 202 else None
        try:
            return r.json()
        except ValueError:
            return r.text

    def _wait_lro(self, r: requests.Response, scope: str) -> Any:
        location = r.headers["Location"]
        delay = int(r.headers.get("Retry-After", "5"))
        while True:
            time.sleep(min(max(delay, 2), 20))
            p = self.session.get(location, headers={"Authorization": f"Bearer {self._token(scope)}"}, timeout=120)
            if p.status_code == 429:
                delay = int(p.headers.get("Retry-After", "30"))
                continue
            data = p.json() if p.content else {}
            status = (data.get("status") or "").lower()
            if status in ("succeeded", "completed"):
                res = self.session.get(location.rstrip("/") + "/result",
                                       headers={"Authorization": f"Bearer {self._token(scope)}"}, timeout=120)
                if res.ok and res.content:
                    try:
                        return res.json()
                    except ValueError:
                        pass
                return data
            if status in ("failed", "cancelled", "deduped"):
                raise FabricApiError(500, "LRO", location, data.get("error") or data)
            delay = int(p.headers.get("Retry-After", "5"))

    # ------------------------------------------------------------ shortcuts
    def get(self, path, **kw):
        return self.request("GET", path, **kw)

    def post(self, path, body=None, **kw):
        return self.request("POST", path, body, **kw)

    def patch(self, path, body=None, **kw):
        return self.request("PATCH", path, body, **kw)

    def put(self, path, body=None, **kw):
        return self.request("PUT", path, body, **kw)

    def delete(self, path, **kw):
        return self.request("DELETE", path, **kw)

    def paged(self, path: str, key: str = "value", **kw) -> Iterator[dict]:
        """Itera colecciones paginadas con continuationToken / continuationUri."""
        url = path
        while url:
            data = self.get(url, **kw) or {}
            yield from data.get(key, []) or []
            url = data.get("continuationUri")
            if not url and data.get("continuationToken"):
                sep = "&" if "?" in path else "?"
                url = f"{path}{sep}continuationToken={data['continuationToken']}"

    def powerbi(self, method: str, path: str, body=None, **kw):
        return self.request(method, path, body, base=POWERBI, scope=POWERBI_SCOPE, **kw)

    # ---------------------------------------------------------------- fake
    def _fake(self, method: str, url: str, body: Any) -> Any:
        if method == "GET":
            if "/admin/domains" in url and url.rstrip("/").endswith("domains"):
                return {"domains": []}
            if url.endswith("/dataAccessRoles"):
                return {"value": []}
            if url.endswith("/capacities"):
                return {"value": [{"id": "fake-capacity", "displayName": "F2 demo", "sku": "F2",
                                   "region": "Spain Central", "state": "Active"}]}
            if "/admin/tenantsettings" in url:
                return {"value": []}
            if "activityevents" in url:
                return {"activityEventEntities": [], "lastResultSet": True}
            return {"value": []}
        if method == "POST" and url.endswith("/bulkCreateTags"):
            return {"tags": [{"id": str(uuid.uuid4()), "displayName": t["displayName"]}
                             for t in body.get("createTagsRequest", [])]}
        if method == "POST" and url.endswith("/bulkSetLabels"):
            return {"itemsChangeLabelStatus": [{"id": i["id"], "type": i["type"], "status": "Succeeded"}
                                               for i in body.get("items", [])]}
        if method == "POST" and isinstance(body, dict) and "displayName" in body:
            return {"id": str(uuid.uuid4()), "displayName": body["displayName"], "type": body.get("type")}
        if method == "POST" and "/jobs/" in url:
            return {"_headers": {"Location": url + "/" + str(uuid.uuid4())}}
        return None
