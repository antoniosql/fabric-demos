# -*- coding: utf-8 -*-
"""Pruebas de coherencia entre las convenciones de nomenclatura y las configuraciones."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "local"))

from run_medallion_local import parse_datetime, parse_decimal, normalize_id  # noqa: E402

PREFIXES = ("LH_", "WH_", "PL_", "NB_", "DF_", "SM_", "ENV_", "WS_", "CAP_")


def test_workspaces_use_valid_prefixes():
    cfg = json.loads((ROOT / "config" / "workspaces.json").read_text(encoding="utf-8"))
    for opt in cfg["design"]["options"].values():
        for ws in opt["workspaces"]:
            assert ws["name"].startswith("WS_"), ws["name"]
            for lh in ws["lakehouses"]:
                assert lh.startswith(("LH_", "WH_")), lh
    assert cfg["capacity"]["name"].startswith("CAP_")


def test_ingestion_configs_have_business_key_and_schema():
    for p in (ROOT / "config" / "ingestion").glob("*.json"):
        c = json.loads(p.read_text(encoding="utf-8"))
        assert c["business_key"], p.name
        assert c["target_schema"] and c["target_table"], p.name
        assert c["target_lakehouse"].startswith("LH_"), p.name


def test_parse_decimal_handles_frasohome_quirks():
    assert parse_decimal("127,74") == 127.74
    assert parse_decimal("€1342.89") == 1342.89
    assert parse_decimal("1.461,32") == 1461.32
    assert parse_decimal("730.66") == 730.66
    assert parse_decimal("") is None


def test_parse_datetime_handles_mixed_formats():
    assert parse_datetime("2025-05-11 15:46:46").year == 2025
    assert parse_datetime("20/03/2024 09:20").month == 3
    assert parse_datetime("13/12/25 11:42").year == 2025
    assert parse_datetime("14 de septiembre de 2025 08:25").month == 9
    assert parse_datetime("10 de Enero de 2022").day == 10


def test_normalize_id():
    assert normalize_id("c0030") == "C0030"
    assert normalize_id(" T-500031") == "T-500031"
