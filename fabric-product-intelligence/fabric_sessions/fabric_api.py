from __future__ import annotations

from dataclasses import dataclass
import base64
import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests


FABRIC_API = "https://api.fabric.microsoft.com/v1"
FABRIC_TOKEN_RESOURCE = "https://api.fabric.microsoft.com"
ONELAKE_DFS = "https://onelake.dfs.fabric.microsoft.com"
ONELAKE_TOKEN_RESOURCE = "https://storage.azure.com/"


class FabricApiError(RuntimeError):
    pass


@dataclass
class FabricClient:
    tenant_id: str
    token: str | None = None
    onelake_token: str | None = None

    def __post_init__(self) -> None:
        if not self.token:
            self.token = _get_token_with_az(FABRIC_TOKEN_RESOURCE)

    def request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        url = path if path.startswith("https://") else f"{FABRIC_API}{path}"
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.token}"
        headers.setdefault("Content-Type", "application/json")
        response = requests.request(method, url, headers=headers, timeout=120, **kwargs)
        if response.status_code >= 400:
            raise FabricApiError(f"{method} {url} failed: {response.status_code} {response.text}")
        if not response.text:
            return {}
        try:
            payload = response.json()
        except json.JSONDecodeError:
            return {"text": response.text}
        if payload is None:
            return {}
        if isinstance(payload, dict):
            return payload
        return {"value": payload}

    def list_workspaces(self) -> list[dict[str, Any]]:
        return self.request("GET", "/workspaces").get("value", [])

    def get_workspace_by_name(self, name: str) -> dict[str, Any] | None:
        for workspace in self.list_workspaces():
            if workspace.get("displayName") == name:
                return workspace
        return None

    def create_workspace(self, name: str, capacity_id: str) -> dict[str, Any]:
        existing = self.get_workspace_by_name(name)
        if existing:
            return existing
        payload = {"displayName": name, "capacityId": capacity_id}
        return self.request("POST", "/workspaces", json=payload)

    def list_items(self, workspace_id: str) -> list[dict[str, Any]]:
        return self.request("GET", f"/workspaces/{workspace_id}/items").get("value", [])

    def get_item_by_name(self, workspace_id: str, name: str, item_type: str) -> dict[str, Any] | None:
        for item in self.list_items(workspace_id):
            if item.get("displayName") == name and item.get("type") == item_type:
                return item
        return None

    def create_item(
        self,
        workspace_id: str,
        name: str,
        item_type: str,
        definition: dict | None = None,
        folder_id: str | None = None,
    ) -> dict:
        existing = self.get_item_by_name(workspace_id, name, item_type)
        if existing:
            return existing
        payload: dict[str, Any] = {"displayName": name, "type": item_type}
        if folder_id:
            payload["folderId"] = folder_id
        if definition:
            payload["definition"] = definition
        created = self.request("POST", f"/workspaces/{workspace_id}/items", json=payload)
        if created:
            return created
        return self.get_item_by_name(workspace_id, name, item_type) or {"displayName": name, "type": item_type}

    def list_folders(self, workspace_id: str) -> list[dict[str, Any]]:
        return self.request("GET", f"/workspaces/{workspace_id}/folders").get("value", [])

    def get_folder_by_name(self, workspace_id: str, name: str) -> dict[str, Any] | None:
        for folder in self.list_folders(workspace_id):
            if folder.get("displayName") == name:
                return folder
        return None

    def create_folder(self, workspace_id: str, name: str) -> dict[str, Any]:
        existing = self.get_folder_by_name(workspace_id, name)
        if existing:
            return existing
        created = self.request("POST", f"/workspaces/{workspace_id}/folders", json={"displayName": name})
        return created or {"displayName": name}

    def create_notebook(self, workspace_id: str, name: str, notebook_path: Path, folder_id: str | None = None) -> dict:
        existing = self.get_item_by_name(workspace_id, name, "Notebook")
        definition = notebook_definition(notebook_path)
        if existing:
            self.update_item_definition(workspace_id, existing["id"], definition)
            return existing
        return self.create_item(workspace_id, name, "Notebook", definition=definition, folder_id=folder_id)

    def update_item_definition(self, workspace_id: str, item_id: str, definition: dict[str, object]) -> dict[str, Any]:
        return self.request(
            "POST",
            f"/workspaces/{workspace_id}/items/{item_id}/updateDefinition",
            json={"definition": definition},
        )

    def run_item_job(self, workspace_id: str, item_id: str, job_type: str) -> dict[str, Any]:
        return self.request(
            "POST",
            f"/workspaces/{workspace_id}/items/{item_id}/jobs/instances",
            params={"jobType": job_type},
            json={},
        )

    def list_item_job_instances(self, workspace_id: str, item_id: str) -> list[dict[str, Any]]:
        return self.request("GET", f"/workspaces/{workspace_id}/items/{item_id}/jobs/instances").get("value", [])

    def run_item_job_and_wait(
        self,
        workspace_id: str,
        item_id: str,
        job_type: str,
        timeout_seconds: int = 3600,
        poll_seconds: int = 15,
    ) -> dict[str, Any]:
        before_ids = {job.get("id") for job in self.list_item_job_instances(workspace_id, item_id)}
        self.run_item_job(workspace_id, item_id, job_type)
        deadline = time.monotonic() + timeout_seconds
        latest: dict[str, Any] | None = None
        while time.monotonic() < deadline:
            jobs = self.list_item_job_instances(workspace_id, item_id)
            new_jobs = [job for job in jobs if job.get("id") not in before_ids]
            candidates = new_jobs or jobs
            if candidates:
                latest = sorted(candidates, key=lambda job: job.get("startTimeUtc", ""), reverse=True)[0]
                status = str(latest.get("status", "")).lower()
                if status in {"completed", "succeeded"}:
                    return latest
                if status in {"failed", "cancelled", "canceled"}:
                    reason = latest.get("failureReason") or {}
                    message = reason.get("message") or latest
                    raise FabricApiError(f"{job_type} failed for item {item_id}: {message}")
            time.sleep(poll_seconds)
        raise FabricApiError(f"{job_type} did not finish within {timeout_seconds} seconds. Last status: {latest}")

    def upload_onelake_file(self, workspace_name: str, lakehouse_name: str, remote_path: str, local_path: Path) -> None:
        if not self.onelake_token:
            self.onelake_token = _get_token_with_az(ONELAKE_TOKEN_RESOURCE)
        headers = {"Authorization": f"Bearer {self.onelake_token}", "x-ms-version": "2023-11-03"}
        self._ensure_onelake_directories(workspace_name, lakehouse_name, Path(remote_path).parent.as_posix(), headers)

        url = _onelake_url(workspace_name, lakehouse_name, remote_path)
        create_response = requests.put(url, headers=headers, params={"resource": "file"}, timeout=120)
        if create_response.status_code not in {200, 201}:
            raise FabricApiError(
                f"Could not create OneLake file for {local_path.name}: "
                f"{create_response.status_code} {create_response.text}"
            )

        data = local_path.read_bytes()
        append_response = requests.patch(
            url,
            headers=headers,
            params={"action": "append", "position": "0"},
            data=data,
            timeout=300,
        )
        if append_response.status_code not in {200, 202}:
            raise FabricApiError(
                f"Could not append OneLake file for {local_path.name}: "
                f"{append_response.status_code} {append_response.text}"
            )

        flush_response = requests.patch(
            url,
            headers=headers,
            params={"action": "flush", "position": str(len(data))},
            timeout=120,
        )
        if flush_response.status_code not in {200, 201}:
            raise FabricApiError(
                f"Could not flush OneLake file for {local_path.name}: "
                f"{flush_response.status_code} {flush_response.text}"
            )

    def _ensure_onelake_directories(
        self, workspace_name: str, lakehouse_name: str, directory_path: str, headers: dict[str, str]
    ) -> None:
        if not directory_path or directory_path == ".":
            return
        current_parts: list[str] = []
        for part in directory_path.split("/"):
            if not part:
                continue
            current_parts.append(part)
            path = "/".join(current_parts)
            response = requests.put(
                _onelake_url(workspace_name, lakehouse_name, path),
                headers=headers,
                params={"resource": "directory"},
                timeout=120,
            )
            if response.status_code in {200, 201, 409}:
                continue
            raise FabricApiError(
                f"Could not create OneLake directory `{path}`: {response.status_code} {response.text}"
            )


def _get_token_with_az(resource: str = FABRIC_TOKEN_RESOURCE) -> str:
    az_path = shutil.which("az")
    if not az_path:
        raise FabricApiError(
            "Azure CLI executable `az` was not found in PATH. Install Azure CLI, restart the "
            "terminal, run `az login`, and try again."
        )
    command = [
        az_path,
        "account",
        "get-access-token",
        "--resource",
        resource,
        "--query",
        "accessToken",
        "-o",
        "tsv",
    ]
    try:
        completed = subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout).strip()
        suffix = f" Azure CLI output: {detail}" if detail else ""
        raise FabricApiError(
            f"Could not obtain a Fabric token with Azure CLI. Run `az login` and try again.{suffix}"
        ) from exc
    token = completed.stdout.strip()
    if not token:
        raise FabricApiError("Azure CLI returned an empty Fabric access token.")
    return token


def _onelake_url(workspace_name: str, lakehouse_name: str, path: str) -> str:
    encoded_workspace = quote(workspace_name.strip("/"), safe="")
    encoded_lakehouse = quote(f"{lakehouse_name.strip('/')}.Lakehouse", safe="")
    encoded_path = quote(path.strip("/"), safe="/")
    return f"{ONELAKE_DFS}/{encoded_workspace}/{encoded_lakehouse}/{encoded_path}"


def notebook_definition(path: Path) -> dict[str, object]:
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return {
        "format": "ipynb",
        "parts": [
            {
                "path": "notebook.ipynb",
                "payload": payload,
                "payloadType": "InlineBase64",
            }
        ],
    }
