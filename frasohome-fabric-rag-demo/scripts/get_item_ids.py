#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List


def run(cmd: List[str]) -> str:
    completed = subprocess.run(cmd, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        print(completed.stderr, file=sys.stderr)
        raise SystemExit(completed.returncode)
    return completed.stdout.strip()


def parse_json_loose(text: str) -> Any:
    text = text.strip()
    start = text.find("{")
    if start < 0:
        start = text.find("[")
    if start > 0:
        text = text[start:]
    return json.loads(text)


def find_item(items_payload: Any, display_name: str, item_type: str | None = None) -> Dict[str, Any] | None:
    if isinstance(items_payload, dict):
        if isinstance(items_payload.get("text"), dict):
            items_payload = items_payload["text"]
        items = items_payload.get("value") or items_payload.get("items") or items_payload.get("data") or []
    else:
        items = items_payload
    for item in items:
        name = item.get("displayName") or item.get("name")
        typ = item.get("type") or item.get("itemType")
        if name == display_name and (item_type is None or typ == item_type):
            return item
    for item in items:
        name = item.get("displayName") or item.get("name") or ""
        if name.lower() == display_name.lower():
            return item
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve Fabric item ids using fab api.")
    parser.add_argument("--workspace-id", default=os.getenv("FABRIC_WORKSPACE_ID"), required=False)
    parser.add_argument("--sql-database-name", default=os.getenv("FABRIC_SQL_DATABASE_NAME"), required=False)
    parser.add_argument("--udf-name", default=os.getenv("FABRIC_UDF_ITEM_NAME", "FrasoHome_RAG_UDF"), required=False)
    parser.add_argument("--out", default=".fabric.generated.env")
    args = parser.parse_args()

    if not args.workspace_id or args.workspace_id.startswith("00000000"):
        raise SystemExit("--workspace-id o FABRIC_WORKSPACE_ID requerido")
    if not args.sql_database_name:
        raise SystemExit("--sql-database-name o FABRIC_SQL_DATABASE_NAME requerido")

    payload = parse_json_loose(run(["fab", "api", f"workspaces/{args.workspace_id}/items", "-X", "get"]))
    sql_item = find_item(payload, args.sql_database_name, "SQLDatabase")
    udf_item = find_item(payload, args.udf_name, "UserDataFunction")

    lines = []
    if sql_item:
        lines.append(f"FABRIC_SQL_DATABASE_ITEM_ID={sql_item.get('id')}")
        print(f"SQL Database item id: {sql_item.get('id')}")
    else:
        print(f"No se encontró SQL Database con nombre {args.sql_database_name}", file=sys.stderr)

    if udf_item:
        lines.append(f"FABRIC_UDF_ITEM_ID={udf_item.get('id')}")
        print(f"UDF item id: {udf_item.get('id')}")

    if lines:
        Path(args.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"Variables escritas en {args.out}")
    else:
        raise SystemExit("No se resolvieron item ids")


if __name__ == "__main__":
    main()
