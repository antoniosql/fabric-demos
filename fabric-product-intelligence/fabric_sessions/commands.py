from __future__ import annotations

import json
import shutil

from .config import REPO_ROOT, STATE_PATH, Settings, require_fabric_settings
from .dataset import EXPECTED_FILES, validate_source_dataset
from .fabric_api import FabricClient, FabricApiError


FABRIC_NOTEBOOK_SEQUENCE = [
    "00_ingest_raw",
    "01_curated_transactions",
    "02_quality_governance",
    "03_features_scoring",
    "04_app_seed_export",
]


def check_prereqs(settings: Settings) -> int:
    issues = validate_source_dataset(settings.source_data_path)
    for issue in issues:
        print(f"[{issue.severity.upper()}] {issue.file}: {issue.message}")
    for executable in ["python", "node", "npm", "az"]:
        found = shutil.which(executable)
        print(f"{executable}: {found or 'not found'}")
    print(f"Source data path: {settings.source_data_path}")
    print(f"Fabric workspace: {settings.fabric_workspace_name}")
    errors = [issue for issue in issues if issue.severity == "error"]
    return 1 if errors else 0


def deploy(settings: Settings) -> int:
    require_fabric_settings(settings)
    client = FabricClient(settings.fabric_tenant_id)
    state = _load_state()
    workspace = client.create_workspace(settings.fabric_workspace_name, settings.fabric_capacity_id)
    workspace_id = workspace["id"]
    state["workspace"] = workspace
    _save_state(state)
    print(f"Workspace ready: {settings.fabric_workspace_name} ({workspace_id})")

    for name, item_type in [
        (settings.fabric_lakehouse_name, "Lakehouse"),
        (settings.fabric_sql_database_name, "SQLDatabase"),
        (settings.fabric_semantic_model_name, "SemanticModel"),
        (settings.fabric_data_agent_name, "DataAgent"),
    ]:
        try:
            if item_type == "SemanticModel":
                item = client.get_item_by_name(workspace_id, name, item_type)
                if item:
                    state[item_type] = item
                    _save_state(state)
                    print(f"{item_type} ready: {name} ({item.get('id', 'pending')})")
                else:
                    tmdl_path = REPO_ROOT / "semantic-model" / "model.tmdl"
                    print(
                        f"Skipping {item_type} `{name}` automatic creation: Fabric requires a "
                        f"semantic model definition. Import or publish {tmdl_path} after the "
                        "Lakehouse tables exist."
                    )
                continue
            item = client.create_item(workspace_id, name, item_type)
            state[item_type] = item
            _save_state(state)
            print(f"{item_type} ready: {name} ({item.get('id', 'pending')})")
        except FabricApiError as exc:
            print(f"Could not create {item_type} `{name}` automatically: {exc}")
            print("Keep this item in .env/state manually if your tenant requires a specialized creation flow.")

    _deploy_notebooks(client, workspace_id, state)
    _save_state(state)
    print(f"State saved to {STATE_PATH}")
    return 0


def _deploy_notebooks(client: FabricClient, workspace_id: str, state: dict) -> None:
    notebook_dir = REPO_ROOT / "notebooks" / "fabric_workspace"
    notebooks = sorted(notebook_dir.glob("*.ipynb"))
    if not notebooks:
        print(f"No Fabric workspace notebooks found under {notebook_dir}")
        return

    folder_name = "Fabric Workspace Notebooks"
    folder_id = None
    try:
        folder = client.create_folder(workspace_id, folder_name)
        folder_id = folder.get("id")
        print(f"Notebook folder ready: {folder_name} ({folder_id or 'pending'})")
    except FabricApiError as exc:
        print(f"Could not create notebook folder `{folder_name}` automatically: {exc}")
        print("Uploading notebooks to the workspace root instead.")

    published = []
    for notebook_path in notebooks:
        notebook_name = notebook_path.stem
        try:
            notebook = client.create_notebook(workspace_id, notebook_name, notebook_path, folder_id=folder_id)
            published.append(notebook)
            print(f"Notebook ready: {notebook_name} ({notebook.get('id', 'pending')})")
        except FabricApiError as exc:
            print(f"Could not upload notebook `{notebook_name}` automatically: {exc}")
            print(f"Import it manually from {notebook_path}.")

    if published:
        state["NotebookFolder"] = {"displayName": folder_name, "id": folder_id}
        state["Notebooks"] = published
        _save_state(state)


def upload_data(settings: Settings) -> int:
    require_fabric_settings(settings)
    issues = validate_source_dataset(settings.source_data_path)
    errors = [issue for issue in issues if issue.severity == "error"]
    if errors:
        for issue in errors:
            print(f"[ERROR] {issue.file}: {issue.message}")
        return 1
    client = FabricClient(settings.fabric_tenant_id)
    for file_name in EXPECTED_FILES:
        local_path = settings.source_data_path / file_name
        remote_path = f"{settings.raw_files_path.strip('/')}/{file_name}"
        print(f"Uploading {file_name} -> {remote_path}")
        client.upload_onelake_file(
            settings.fabric_workspace_name,
            settings.fabric_lakehouse_name,
            remote_path,
            local_path,
        )
    _run_fabric_notebook(client, settings, "00_ingest_raw", timeout_seconds=1800)
    return 0


def run_notebooks(settings: Settings) -> int:
    require_fabric_settings(settings)
    client = FabricClient(settings.fabric_tenant_id)
    for notebook_name in FABRIC_NOTEBOOK_SEQUENCE:
        _run_fabric_notebook(client, settings, notebook_name)
    return 0


def validate_demo(settings: Settings) -> int:
    issues = validate_source_dataset(settings.source_data_path)
    if any(issue.severity == "error" for issue in issues):
        for issue in issues:
            print(f"[{issue.severity.upper()}] {issue.file}: {issue.message}")
        return 1
    require_fabric_settings(settings)
    client = FabricClient(settings.fabric_tenant_id)
    workspace = client.get_workspace_by_name(settings.fabric_workspace_name)
    if not workspace:
        print(f"[ERROR] Fabric workspace not found: {settings.fabric_workspace_name}")
        return 1
    required_items = [
        (settings.fabric_lakehouse_name, "Lakehouse"),
        (settings.fabric_sql_database_name, "SQLDatabase"),
        (settings.fabric_data_agent_name, "DataAgent"),
    ]
    missing = []
    for name, item_type in required_items:
        if not client.get_item_by_name(workspace["id"], name, item_type):
            missing.append(f"{item_type}:{name}")
    for notebook_name in FABRIC_NOTEBOOK_SEQUENCE:
        if not client.get_item_by_name(workspace["id"], notebook_name, "Notebook"):
            missing.append(f"Notebook:{notebook_name}")
    if missing:
        print("[ERROR] Missing Fabric artifacts:")
        for item in missing:
            print(f"  - {item}")
        return 1

    print("Fabric artifacts are present.")
    failed_jobs = []
    for notebook_name in FABRIC_NOTEBOOK_SEQUENCE:
        notebook = client.get_item_by_name(workspace["id"], notebook_name, "Notebook")
        jobs = client.list_item_job_instances(workspace["id"], notebook["id"])
        latest = sorted(jobs, key=lambda job: job.get("startTimeUtc", ""), reverse=True)[0] if jobs else None
        if latest:
            print(f"{notebook_name}: latest job {latest.get('status')} at {latest.get('startTimeUtc')}")
            if str(latest.get("status", "")).lower() in {"failed", "cancelled", "canceled"}:
                failed_jobs.append(notebook_name)
        else:
            print(f"{notebook_name}: no Fabric execution recorded yet")
    if failed_jobs:
        print("[ERROR] Some Fabric notebook jobs failed:")
        for notebook_name in failed_jobs:
            print(f"  - {notebook_name}")
        return 1
    return 0


def _run_fabric_notebook(
    client: FabricClient,
    settings: Settings,
    notebook_name: str,
    timeout_seconds: int = 3600,
) -> None:
    workspace = client.get_workspace_by_name(settings.fabric_workspace_name)
    if not workspace:
        raise FabricApiError(f"Fabric workspace not found: {settings.fabric_workspace_name}")
    notebook = client.get_item_by_name(workspace["id"], notebook_name, "Notebook")
    if not notebook:
        raise FabricApiError(
            f"Fabric notebook `{notebook_name}` was not found. Run `python -m fabric_sessions deploy` first."
        )
    print(f"Running Fabric notebook `{notebook_name}`...")
    job = client.run_item_job_and_wait(
        workspace["id"],
        notebook["id"],
        "RunNotebook",
        timeout_seconds=timeout_seconds,
    )
    print(f"Fabric notebook `{notebook_name}` finished with status {job.get('status')}.")


def _load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {}


def _save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
