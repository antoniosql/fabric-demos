#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Render Fabric UDF definition and fab deploy config.")
    parser.add_argument("--workspace-id", default=os.getenv("FABRIC_WORKSPACE_ID"))
    parser.add_argument("--sql-database-item-id", default=os.getenv("FABRIC_SQL_DATABASE_ITEM_ID"))
    parser.add_argument("--sql-alias", default=os.getenv("FABRIC_UDF_SQL_ALIAS", "frasohomesql"))
    parser.add_argument("--items-dir", default="fabric/items")
    args = parser.parse_args()

    if not args.workspace_id or args.workspace_id.startswith("00000000"):
        raise SystemExit("workspace id requerido")
    if not args.sql_database_item_id or args.sql_database_item_id.startswith("00000000"):
        raise SystemExit("sql database item id requerido")
    if not args.sql_alias or not args.sql_alias.isalnum():
        raise SystemExit("sql alias requerido: usa solo caracteres alfanuméricos, sin guiones ni barras bajas")

    udf_dir = Path(args.items_dir) / "FrasoHome_RAG_UDF.UserDataFunction"
    template_path = udf_dir / "definition.json.template"
    definition = json.loads(template_path.read_text(encoding="utf-8"))
    definition["connectedDataSources"][0]["alias"] = args.sql_alias
    definition["connectedDataSources"][0]["artifactId"] = args.sql_database_item_id
    definition["connectedDataSources"][0]["workspaceId"] = args.workspace_id
    (udf_dir / "definition.json").write_text(json.dumps(definition, indent=2), encoding="utf-8")

    functions_metadata = {
        "Runtime": "PYTHON",
        "FunctionsMetadata": [
            {
                "Name": "healthCheck",
                "ScriptFile": "function_app.py",
                "Bindings": [
                    {
                        "Methods": ["post"],
                        "Route": "healthCheck",
                        "AuthLevel": "Anonymous",
                        "Name": "req",
                        "Direction": "In",
                        "Type": "HttpTrigger",
                    }
                ],
                "FabricProperties": {
                    "fabricFunctionParameters": [],
                    "fabricFunctionReturnType": "dict",
                },
            },
            {
                "Name": "getReturnCaseContext",
                "ScriptFile": "function_app.py",
                "Bindings": [
                    {
                        "Methods": ["post"],
                        "Route": "getReturnCaseContext",
                        "AuthLevel": "Anonymous",
                        "Name": "req",
                        "Direction": "In",
                        "Type": "HttpTrigger",
                    },
                    {
                        "ItemType": None,
                        "SubType": "",
                        "Alias": args.sql_alias,
                        "Name": "sqlDB",
                        "Direction": "In",
                        "Type": "FabricItem",
                    },
                ],
                "FabricProperties": {
                    "fabricFunctionParameters": [
                        {"dataType": "str", "name": "returnCaseId"},
                    ],
                    "fabricFunctionReturnType": "dict",
                },
            },
            {
                "Name": "answerReturnCase",
                "ScriptFile": "function_app.py",
                "Bindings": [
                    {
                        "Methods": ["post"],
                        "Route": "answerReturnCase",
                        "AuthLevel": "Anonymous",
                        "Name": "req",
                        "Direction": "In",
                        "Type": "HttpTrigger",
                    },
                    {
                        "ItemType": None,
                        "SubType": "",
                        "Alias": args.sql_alias,
                        "Name": "sqlDB",
                        "Direction": "In",
                        "Type": "FabricItem",
                    },
                ],
                "FabricProperties": {
                    "fabricFunctionParameters": [
                        {"dataType": "str", "name": "returnCaseId"},
                        {"dataType": "str", "name": "question"},
                        {"dataType": "int", "name": "maxChunks"},
                    ],
                    "fabricFunctionReturnType": "dict",
                },
            },
        ],
    }
    resources_dir = udf_dir / ".resources"
    resources_dir.mkdir(exist_ok=True)
    (resources_dir / "functions.json").write_text(
        json.dumps(functions_metadata, indent=2),
        encoding="utf-8",
    )

    function_app = udf_dir / "function_app.py"
    app_text = function_app.read_text(encoding="utf-8")
    lines = []
    for line in app_text.splitlines():
        if line.startswith("SQL_ALIAS = "):
            lines.append(f"SQL_ALIAS = {args.sql_alias!r}")
        else:
            lines.append(line)
    function_app.write_text("\n".join(lines) + "\n", encoding="utf-8")

    config = f"""core:
  workspace_id: \"{args.workspace_id}\"
  repository_directory: \".\"
  item_type_in_scope:
    - UserDataFunction
"""
    (Path(args.items_dir) / "config.yml").write_text(config, encoding="utf-8")

    print(f"Render OK: {udf_dir / 'definition.json'}")
    print(f"Render OK: {udf_dir / '.resources' / 'functions.json'}")
    print(f"Render OK: {Path(args.items_dir) / 'config.yml'}")


if __name__ == "__main__":
    main()
