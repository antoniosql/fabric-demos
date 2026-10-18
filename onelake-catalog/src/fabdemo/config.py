"""Carga de configuración (config/config.toml) y estado del despliegue (.state/state.json)."""
from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "config.toml"
STATE_PATH = ROOT / ".state" / "state.json"
ZERO = "00000000-0000-0000-0000-000000000000"


@dataclass
class Config:
    raw: dict

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        path = path or CONFIG_PATH
        if not path.exists():
            raise SystemExit(
                f"No existe {path}. Copia config/config.example.toml a config/config.toml y rellénalo."
            )
        with path.open("rb") as f:
            return cls(tomllib.load(f))

    def get(self, dotted: str, default=None):
        node = self.raw
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    @property
    def prefix(self) -> str:
        return self.get("naming.prefix", "MIDP")

    def ws_name(self, key: str) -> str:
        return f"{self.prefix}-{self.get(f'workspaces.{key}')}"

    @property
    def domain_name(self) -> str:
        return f"{self.prefix} {self.get('domain.name')}"

    def unset_values(self) -> list[str]:
        """Claves que siguen con el GUID de ejemplo."""
        out = []

        def walk(node, path):
            if isinstance(node, dict):
                for k, v in node.items():
                    walk(v, f"{path}.{k}" if path else k)
            elif node == ZERO:
                out.append(path)

        walk(self.raw, "")
        return out


@dataclass
class State:
    data: dict = field(default_factory=dict)
    path: Path = STATE_PATH

    @classmethod
    def load(cls, dry_run: bool = False) -> "State":
        # En dry-run se usa un fichero aparte para no mezclar IDs ficticios con los reales
        path = STATE_PATH.with_name("state.dryrun.json") if dry_run else STATE_PATH
        if path.exists():
            return cls(json.loads(path.read_text(encoding="utf-8")), path)
        return cls({}, path)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")

    def get(self, key: str, default=None):
        return self.data.get(key, default)

    def set(self, key: str, value) -> None:
        self.data[key] = value
        self.save()

    def require(self, key: str):
        if key not in self.data:
            raise SystemExit(f"Falta '{key}' en el estado. ¿Has ejecutado `fabdemo deploy`?")
        return self.data[key]


_PLACEHOLDER = re.compile(r"\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}")


def render(template: str, cfg: Config, state: State) -> str:
    """Sustituye {{ws.x}}, {{group.x}}, {{label.x}}, {{tenant_id}}, {{capacity_id}}."""

    def resolve(key: str) -> str:
        kind, _, name = key.partition(".")
        if kind == "ws":
            return state.require("workspaces")[name]
        if kind == "group":
            return cfg.get(f"groups.{name}")
        if kind == "label":
            return cfg.get(f"labels.{name}")
        if kind == "state":
            return str(state.require(name))
        if key == "tenant_id":
            return cfg.get("tenant.tenant_id")
        if key == "capacity_id":
            return cfg.get("tenant.capacity_id")
        raise KeyError(f"Placeholder desconocido: {{{{{key}}}}}")

    return _PLACEHOLDER.sub(lambda m: resolve(m.group(1)), template)
