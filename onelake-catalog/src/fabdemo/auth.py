"""Credenciales: presentador (admin) y personas de prueba."""
from __future__ import annotations

import os

from azure.identity import (
    AzureCliCredential,
    ClientSecretCredential,
    DeviceCodeCredential,
    InteractiveBrowserCredential,
)

from .config import Config

FABRIC_SCOPE = "https://api.fabric.microsoft.com/.default"
POWERBI_SCOPE = "https://analysis.windows.net/powerbi/api/.default"
STORAGE_SCOPE = "https://storage.azure.com/.default"


def admin_credential(cfg: Config):
    tenant = cfg.get("tenant.tenant_id")
    mode = cfg.get("auth.mode", "cli")
    if mode == "cli":
        return AzureCliCredential(tenant_id=tenant)
    if mode == "browser":
        return InteractiveBrowserCredential(tenant_id=tenant)
    if mode == "devicecode":
        return DeviceCodeCredential(tenant_id=tenant)
    raise SystemExit(f"auth.mode desconocido: {mode}")


def persona_credential(cfg: Config, name: str):
    p = cfg.get(f"personas.{name}")
    if not p:
        raise SystemExit(f"No hay persona '{name}' en config.toml ([personas.{name}]).")
    tenant = cfg.get("tenant.tenant_id")
    if p.get("type") == "sp":
        secret = os.environ.get(p.get("secret_env", ""))
        if not secret:
            raise SystemExit(f"Define la variable de entorno {p.get('secret_env')} con el secreto de '{name}'.")
        return ClientSecretCredential(tenant, p["client_id"], secret)
    if p.get("type") == "browser":
        print(f"Inicia sesión como '{name}' (usa otra cuenta, mejor en una ventana InPrivate).")
        return InteractiveBrowserCredential(tenant_id=tenant, login_hint=p.get("login_hint"))
    raise SystemExit(f"Tipo de persona no soportado: {p.get('type')}")
