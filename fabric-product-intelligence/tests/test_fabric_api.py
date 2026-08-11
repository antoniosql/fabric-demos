import subprocess
from pathlib import Path

import pytest

import fabric_sessions.fabric_api as fabric_api
from fabric_sessions.fabric_api import FabricApiError, FabricClient, _get_token_with_az, notebook_definition


class _Response:
    def __init__(self, text, payload, status_code=200):
        self.text = text
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


def test_get_token_reports_missing_azure_cli(monkeypatch):
    monkeypatch.setattr(fabric_api.shutil, "which", lambda command: None)

    with pytest.raises(FabricApiError, match="az.*not found in PATH"):
        _get_token_with_az()


def test_get_token_includes_azure_cli_error(monkeypatch):
    monkeypatch.setattr(fabric_api.shutil, "which", lambda command: "C:/az.cmd")

    def failed_command(*args, **kwargs):
        raise subprocess.CalledProcessError(1, args[0], stderr="Please run az login")

    monkeypatch.setattr(subprocess, "run", failed_command)

    with pytest.raises(FabricApiError, match="Please run az login"):
        _get_token_with_az()


def test_get_token_runs_resolved_azure_cli_path(monkeypatch):
    monkeypatch.setattr(fabric_api.shutil, "which", lambda command: "C:/az.cmd")

    def successful_command(command, **kwargs):
        assert command[0] == "C:/az.cmd"
        return subprocess.CompletedProcess(command, 0, stdout="token\n", stderr="")

    monkeypatch.setattr(subprocess, "run", successful_command)

    assert _get_token_with_az() == "token"


def test_get_token_uses_requested_resource(monkeypatch):
    monkeypatch.setattr(fabric_api.shutil, "which", lambda command: "C:/az.cmd")

    def successful_command(command, **kwargs):
        assert command[command.index("--resource") + 1] == "https://storage.azure.com/"
        return subprocess.CompletedProcess(command, 0, stdout="storage-token\n", stderr="")

    monkeypatch.setattr(subprocess, "run", successful_command)

    assert _get_token_with_az("https://storage.azure.com/") == "storage-token"


def test_request_normalizes_json_null_response(monkeypatch):
    def null_response(*args, **kwargs):
        return _Response("null", None)

    monkeypatch.setattr(fabric_api.requests, "request", null_response)

    client = FabricClient("tenant", token="token")

    assert client.request("POST", "/workspaces/ws/items") == {}


def test_create_item_returns_pending_placeholder_for_empty_response(monkeypatch):
    responses = [
        _Response('{"value":[]}', {"value": []}),
        _Response("null", None),
        _Response('{"value":[]}', {"value": []}),
    ]

    def next_response(*args, **kwargs):
        return responses.pop(0)

    monkeypatch.setattr(fabric_api.requests, "request", next_response)

    client = FabricClient("tenant", token="token")

    assert client.create_item("ws", "sqldb", "SQLDatabase") == {
        "displayName": "sqldb",
        "type": "SQLDatabase",
    }


def test_upload_onelake_file_uses_storage_token(monkeypatch, tmp_path: Path):
    local_file = tmp_path / "crm.csv"
    local_file.write_bytes(b"id,name\n1,Ana\n")

    token_requests = []

    def token_for_resource(resource):
        token_requests.append(resource)
        return "storage-token"

    put_calls = []
    patch_calls = []

    def ok_put(url, headers, params, timeout):
        assert headers["Authorization"] == "Bearer storage-token"
        put_calls.append((url, params, timeout))
        return _Response("", {})

    def ok_patch(url, headers, params, timeout, data=None):
        assert url == (
            "https://onelake.dfs.fabric.microsoft.com/workspace/lakehouse.Lakehouse/Files/raw/crm.csv"
        )
        assert headers["Authorization"] == "Bearer storage-token"
        patch_calls.append((params, timeout, data))
        return _Response("", {})

    monkeypatch.setattr(fabric_api, "_get_token_with_az", token_for_resource)
    monkeypatch.setattr(fabric_api.requests, "put", ok_put)
    monkeypatch.setattr(fabric_api.requests, "patch", ok_patch)

    client = FabricClient("tenant", token="fabric-token")
    client.upload_onelake_file("workspace", "lakehouse", "Files/raw/crm.csv", local_file)

    assert token_requests == ["https://storage.azure.com/"]
    assert put_calls == [
        (
            "https://onelake.dfs.fabric.microsoft.com/workspace/lakehouse.Lakehouse/Files",
            {"resource": "directory"},
            120,
        ),
        (
            "https://onelake.dfs.fabric.microsoft.com/workspace/lakehouse.Lakehouse/Files/raw",
            {"resource": "directory"},
            120,
        ),
        (
            "https://onelake.dfs.fabric.microsoft.com/workspace/lakehouse.Lakehouse/Files/raw/crm.csv",
            {"resource": "file"},
            120,
        ),
    ]
    assert patch_calls == [
        ({"action": "append", "position": "0"}, 300, b"id,name\n1,Ana\n"),
        ({"action": "flush", "position": "14"}, 120, None),
    ]


def test_notebook_definition_uses_inline_ipynb_payload(tmp_path: Path):
    notebook = tmp_path / "demo.ipynb"
    notebook.write_text('{"nbformat":4}', encoding="utf-8")

    assert notebook_definition(notebook) == {
        "format": "ipynb",
        "parts": [
            {
                "path": "notebook.ipynb",
                "payload": "eyJuYmZvcm1hdCI6NH0=",
                "payloadType": "InlineBase64",
            }
        ],
    }
