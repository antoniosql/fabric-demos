#!/usr/bin/env python3
import argparse
import base64
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List


def run(cmd: List[str]) -> Dict[str, Any]:
    completed = subprocess.run(cmd, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        print(completed.stdout, file=sys.stderr)
        print(completed.stderr, file=sys.stderr)
        raise SystemExit(completed.returncode)

    text = completed.stdout.strip()
    start = text.find("{")
    if start > 0:
        text = text[start:]
    return json.loads(text)


def encode_part(path: Path, part_path: str) -> Dict[str, str]:
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return {
        "path": part_path,
        "payload": payload,
        "payloadType": "InlineBase64",
    }


def wait_for_operation(operation_id: str) -> None:
    for _ in range(30):
        result = run(["fab", "api", f"operations/{operation_id}", "-X", "get"])
        text = result.get("text") or {}
        status = text.get("status")
        if status == "Succeeded":
            return
        if status in {"Failed", "Cancelled"}:
            raise SystemExit(f"updateDefinition falló: {json.dumps(text, ensure_ascii=False)}")
        time.sleep(5)
    raise SystemExit(f"Timeout esperando operación Fabric: {operation_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Update Fabric UDF item definition through Fabric API.")
    parser.add_argument("--workspace-id", required=True)
    parser.add_argument("--udf-item-id", required=True)
    parser.add_argument("--item-dir", default="fabric/items/FrasoHome_RAG_UDF.UserDataFunction")
    parser.add_argument("--payload-out", default="fabric/.deploy/update-definition.json")
    args = parser.parse_args()

    item_dir = Path(args.item_dir)
    parts = [
        encode_part(item_dir / "function_app.py", "function_app.py"),
        encode_part(item_dir / "definition.json", "definition.json"),
        encode_part(item_dir / ".resources" / "functions.json", ".resources/functions.json"),
    ]
    payload_path = Path(args.payload_out)
    payload_path.parent.mkdir(parents=True, exist_ok=True)
    payload_path.write_text(json.dumps({"definition": {"parts": parts}}, indent=2), encoding="utf-8")

    response = run(
        [
            "fab",
            "api",
            f"workspaces/{args.workspace_id}/userDataFunctions/{args.udf_item_id}/updateDefinition",
            "-X",
            "post",
            "-i",
            str(payload_path),
            "--show_headers",
        ]
    )

    status_code = response.get("status_code")
    if status_code == 202:
        headers = response.get("headers") or {}
        operation_id = headers.get("x-ms-operation-id")
        if not operation_id:
            raise SystemExit("Fabric devolvió 202 pero no incluyó x-ms-operation-id.")
        wait_for_operation(operation_id)
    elif status_code not in {200, 201}:
        raise SystemExit(f"updateDefinition devolvió HTTP {status_code}: {json.dumps(response, ensure_ascii=False)}")

    print("UDF definition updated through Fabric API.")


if __name__ == "__main__":
    main()
