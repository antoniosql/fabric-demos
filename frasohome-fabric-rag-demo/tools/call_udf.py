#!/usr/bin/env python3
import argparse
import json
import os
from typing import Any, Dict

import requests
from azure.identity import (
    ClientSecretCredential,
    DefaultAzureCredential,
    InteractiveBrowserCredential,
    ManagedIdentityCredential,
)
from dotenv import load_dotenv

DEFAULT_QUESTION = (
    "El cliente quiere devolver un sofá modular comprado online hace 34 días. "
    "Indica que llegó con una pata dañada, conserva fotos del embalaje y solicita reemplazo urgente. "
    "¿Debemos aprobar devolución, reemplazo o revisión manual?"
)


def require_value(name: str, value: str | None) -> str:
    if not value:
        raise ValueError(f"Falta configurar {name}.")
    return value


def build_credential(args: argparse.Namespace):
    mode = (args.auth_mode or os.getenv("FABRIC_UDF_AUTH_MODE") or "service-principal").lower()
    tenant_id = args.tenant or os.getenv("FABRIC_TENANT_ID") or os.getenv("FAB_TENANT_ID")
    service_principal_client_id = args.client_id or os.getenv("FAB_SPN_CLIENT_ID")
    frontend_tenant_id = args.tenant or os.getenv("VITE_ENTRA_TENANT_ID") or tenant_id
    frontend_client_id = args.client_id or os.getenv("VITE_ENTRA_CLIENT_ID")

    if mode == "service-principal":
        client_secret = args.client_secret or os.getenv("FAB_SPN_CLIENT_SECRET")
        return (
            ClientSecretCredential(
                tenant_id=require_value("FABRIC_TENANT_ID", tenant_id),
                client_id=require_value("FAB_SPN_CLIENT_ID", service_principal_client_id),
                client_secret=require_value("FAB_SPN_CLIENT_SECRET", client_secret),
            ),
            "https://analysis.windows.net/powerbi/api/.default",
        )

    if mode == "managed-identity":
        managed_identity_client_id = (
            args.managed_identity_client_id
            or os.getenv("FABRIC_UDF_MANAGED_IDENTITY_CLIENT_ID")
            or os.getenv("FAB_SPN_CLIENT_ID")
        )
        return (
            ManagedIdentityCredential(client_id=managed_identity_client_id or None),
            "https://analysis.windows.net/powerbi/api/.default",
        )

    if mode == "default":
        return (
            DefaultAzureCredential(exclude_interactive_browser_credential=True),
            "https://analysis.windows.net/powerbi/api/.default",
        )

    if mode == "interactive":
        return (
            InteractiveBrowserCredential(
                tenant_id=require_value("VITE_ENTRA_TENANT_ID or FABRIC_TENANT_ID", frontend_tenant_id),
                client_id=require_value("VITE_ENTRA_CLIENT_ID", frontend_client_id),
            ),
            "https://analysis.windows.net/powerbi/api/.default",
        )

    raise ValueError("FABRIC_UDF_AUTH_MODE debe ser service-principal, managed-identity, default o interactive.")


def invoke(url: str, args: argparse.Namespace, payload: Dict[str, Any]) -> Dict[str, Any]:
    credential, scope = build_credential(args)
    token = credential.get_token(scope)
    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {token.token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=60,
    )
    if not response.ok:
        raise RuntimeError(
            f"HTTP {response.status_code} {response.reason}: {response.text}"
        )
    data = response.json()
    return data.get("output", data)


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Invoke FraSoHome UDF public endpoint.")
    parser.add_argument("--url", default=os.getenv("VITE_UDF_FUNCTION_URL"), required=False)
    parser.add_argument("--auth-mode", choices=["service-principal", "managed-identity", "default", "interactive"])
    parser.add_argument("--tenant")
    parser.add_argument("--client-id")
    parser.add_argument("--client-secret")
    parser.add_argument("--managed-identity-client-id")
    parser.add_argument("--return-case-id", default="RET-2026-004219")
    parser.add_argument("--question", default=DEFAULT_QUESTION)
    args = parser.parse_args()

    url = require_value("VITE_UDF_FUNCTION_URL", args.url)
    result = invoke(
        url,
        args,
        {
            "returnCaseId": args.return_case_id,
            "question": args.question,
            "maxChunks": 6,
        },
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
