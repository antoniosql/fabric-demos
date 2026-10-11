from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = REPO_ROOT / "work" / "generated" / "fabric_state.json"
# Copia versionada de los CSV de FraSoHome (sincronizada con antoniosql/frasohome-demos).
DEFAULT_SOURCE_DATA_PATH = REPO_ROOT / "data" / "retail_omnicanal"


@dataclass(frozen=True)
class Settings:
    fabric_tenant_id: str
    fabric_capacity_id: str
    fabric_workspace_name: str
    fabric_lakehouse_name: str
    fabric_sql_database_name: str
    fabric_semantic_model_name: str
    fabric_data_agent_name: str
    fabric_app_name: str
    source_data_path: Path
    raw_files_path: str
    quality_score_threshold: float
    ml_target_days: int

    @property
    def generated_dir(self) -> Path:
        return REPO_ROOT / "work" / "generated"


def _get(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _resolve_data_path(value: str) -> Path:
    """Ruta de los CSV: la de SOURCE_DATA_PATH si se indica (relativa a la demo) o la copia del repo."""
    if not value:
        return DEFAULT_SOURCE_DATA_PATH
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


def load_settings(env_path: Path | None = None) -> Settings:
    load_dotenv(env_path or REPO_ROOT / ".env")
    return Settings(
        fabric_tenant_id=_get("FABRIC_TENANT_ID"),
        fabric_capacity_id=_get("FABRIC_CAPACITY_ID"),
        fabric_workspace_name=_get("FABRIC_WORKSPACE_NAME", "fabric-retail-sessions-dev"),
        fabric_lakehouse_name=_get("FABRIC_LAKEHOUSE_NAME", "lh_retail_omnicanal"),
        fabric_sql_database_name=_get("FABRIC_SQL_DATABASE_NAME", "sqldb_fabric_sessions_ops"),
        fabric_semantic_model_name=_get("FABRIC_SEMANTIC_MODEL_NAME", "sm_retail_sessions"),
        fabric_data_agent_name=_get("FABRIC_DATA_AGENT_NAME", "agent_retail_business"),
        fabric_app_name=_get("FABRIC_APP_NAME", "app_retail_sessions"),
        source_data_path=_resolve_data_path(_get("SOURCE_DATA_PATH")),
        raw_files_path=_get("RAW_FILES_PATH", "Files/raw"),
        quality_score_threshold=float(_get("QUALITY_SCORE_THRESHOLD", "95")),
        ml_target_days=int(_get("ML_TARGET_DAYS", "60")),
    )


def require_fabric_settings(settings: Settings) -> None:
    missing = []
    if not settings.fabric_tenant_id:
        missing.append("FABRIC_TENANT_ID")
    if not settings.fabric_capacity_id:
        missing.append("FABRIC_CAPACITY_ID")
    if missing:
        names = ", ".join(missing)
        raise SystemExit(f"Missing required Fabric settings in .env: {names}")
