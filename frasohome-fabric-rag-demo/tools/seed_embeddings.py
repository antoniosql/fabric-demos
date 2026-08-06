#!/usr/bin/env python3
"""
Genera embeddings deterministas de demo y los guarda en un JSON local.

Este script es opcional. El flujo principal usa recuperación T-SQL. Sirve para enseñar
cómo se ve un vector de embedding aunque aún no tengas vector search habilitado en SQL.

Para insertar documentos, chunks y embeddings en rag.Documents, rag.Chunks y
rag.ChunkEmbeddings usa tools/ingest_policy_markdown.py.
"""
import argparse
import hashlib
import json
import math
import os
import re
import urllib.request
from typing import Iterable, List


def embed(text: str, dimensions: int = 64) -> List[float]:
    vec = [0.0] * dimensions
    tokens = re.findall(r"[\wáéíóúüñ]+", text.lower())
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [round(v / norm, 6) for v in vec]


def _use_azure_openai(provider: str | None = None) -> bool:
    configured_provider = (provider or os.getenv("RAG_EMBEDDING_PROVIDER") or "").lower()
    use_external = (os.getenv("RAG_USE_EXTERNAL_MODELS") or "false").lower() == "true"
    return configured_provider == "azure-openai" or (use_external and configured_provider in {"", "azure-openai"})


def embed_with_azure_openai(text: str) -> List[float]:
    endpoint = (os.getenv("AZURE_OPENAI_ENDPOINT") or "").rstrip("/")
    deployment = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT") or ""
    api_key = os.getenv("AZURE_OPENAI_API_KEY") or ""
    api_version = os.getenv("AZURE_OPENAI_API_VERSION") or "2024-10-21"

    if not endpoint or not deployment or not api_key:
        raise ValueError(
            "Para usar embeddings reales configura AZURE_OPENAI_ENDPOINT, "
            "AZURE_OPENAI_EMBEDDING_DEPLOYMENT y AZURE_OPENAI_API_KEY."
        )

    payload: dict[str, object] = {"input": text}
    requested_dimensions = os.getenv("AZURE_OPENAI_EMBEDDING_DIMENSIONS")
    if requested_dimensions:
        payload["dimensions"] = int(requested_dimensions)

    request = urllib.request.Request(
        f"{endpoint}/openai/deployments/{deployment}/embeddings?api-version={api_version}",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "api-key": api_key,
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        data = json.loads(response.read().decode("utf-8"))
    return [float(v) for v in data["data"][0]["embedding"]]


def embed_text(text: str, dimensions: int = 64, provider: str | None = None) -> List[float]:
    if _use_azure_openai(provider):
        return embed_with_azure_openai(text)
    return embed(text, dimensions)


def resolve_embedding_model(default_model: str = "demo-hash-embedding-v1", provider: str | None = None) -> str:
    if _use_azure_openai(provider):
        return os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT") or "azure-openai-embedding"
    return os.getenv("RAG_EMBEDDING_MODEL") or default_model


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dimensions", type=int, default=int(os.getenv("RAG_EMBEDDING_DIMENSIONS", "64")))
    parser.add_argument("--provider", choices=["demo", "azure-openai"], default=os.getenv("RAG_EMBEDDING_PROVIDER"))
    parser.add_argument("--out", default="embeddings.preview.json")
    parser.add_argument("texts", nargs="*")
    args = parser.parse_args()
    texts = args.texts or [
        "daños en transporte con evidencia fotográfica",
        "muebles voluminosos con stock de reemplazo",
        "clientes Gold con bajo riesgo",
    ]
    payload = [{"text": t, "embedding": embed_text(t, args.dimensions, args.provider)} for t in texts]
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
