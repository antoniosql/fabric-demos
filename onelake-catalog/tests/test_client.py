"""Pruebas del cliente REST sin tenant: 429, LRO, paginación y errores."""
import json
from unittest import mock

import pytest

import fabdemo.client as client_mod
from fabdemo.client import FabricApiError, FabricClient


class Tok:
    token, expires_on = "t", 9e12


class Cred:
    def get_token(self, scope):
        return Tok()


def resp(status, body=None, headers=None):
    r = mock.Mock()
    r.status_code = status
    r.headers = headers or {}
    r.content = json.dumps(body).encode() if body is not None else b""
    r.json = lambda: body
    r.text = json.dumps(body)
    r.ok = status < 400
    return r


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(client_mod.time, "sleep", lambda s: None)


def test_retry_429_then_ok():
    c = FabricClient(Cred())
    c.session.request = mock.Mock(side_effect=[resp(429, {}, {"Retry-After": "1"}), resp(200, {"id": "x"})])
    assert c.get("/workspaces/1") == {"id": "x"}
    assert c.session.request.call_count == 2


def test_lro_returns_result():
    c = FabricClient(Cred())
    c.session.request = mock.Mock(return_value=resp(202, None, {"Location": "https://op/1", "Retry-After": "1"}))
    c.session.get = mock.Mock(side_effect=[resp(200, {"status": "Running"}), resp(200, {"status": "Succeeded"}),
                                           resp(200, {"id": "new"})])
    assert c.post("/workspaces/1/items", {"displayName": "a"}) == {"id": "new"}


def test_lro_failure_raises():
    c = FabricClient(Cred())
    c.session.request = mock.Mock(return_value=resp(202, None, {"Location": "https://op/1"}))
    c.session.get = mock.Mock(return_value=resp(200, {"status": "Failed", "error": {"errorCode": "Boom"}}))
    with pytest.raises(FabricApiError):
        c.post("/x", {})


def test_pagination():
    c = FabricClient(Cred())
    c.session.request = mock.Mock(side_effect=[
        resp(200, {"value": [{"id": 1}], "continuationToken": "abc"}),
        resp(200, {"value": [{"id": 2}]}),
    ])
    assert [i["id"] for i in c.paged("/workspaces")] == [1, 2]


def test_error_code_parsed():
    c = FabricClient(Cred())
    c.session.request = mock.Mock(return_value=resp(403, {"errorCode": "InsufficientPrivileges", "message": "no"}))
    with pytest.raises(FabricApiError) as e:
        c.post("/workspaces/1/items", {"displayName": "a", "type": "Notebook"})
    assert e.value.code == "InsufficientPrivileges" and e.value.status == 403


def test_policy_files_render():
    from fabdemo.config import Config, State
    from fabdemo.policies import POLICY_DIR, load_policy
    cfg = Config({"groups": {"ingenieros_prod": "g1"}})
    st = State({"workspaces": {"prod_analytics": "w1", "prod_reporting": "w2"}})
    for f in POLICY_DIR.glob("*.json"):
        p = load_policy(f, cfg, st)
        assert p["policyRules"] and "{{" not in json.dumps(p)
