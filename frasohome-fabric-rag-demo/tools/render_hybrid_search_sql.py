#!/usr/bin/env python3
"""
Renderiza una consulta SQL para ejecutar búsqueda híbrida real:
score lexical T-SQL + similitud vectorial contra rag.ChunkEmbeddings.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from seed_embeddings import embed_text, resolve_embedding_model


DEFAULT_QUESTION = (
    "El cliente Gold quiere devolver un sofá modular comprado online hace 34 días. "
    "Indica que llegó con una pata dañada, conserva fotos del embalaje y solicita reemplazo urgente. "
    "¿Debemos aprobar devolución, reemplazo o revisión manual?"
)


def sql_string(value: str, unicode: bool = True) -> str:
    prefix = "N" if unicode else ""
    return f"{prefix}'{value.replace(chr(39), chr(39) + chr(39))}'"


def render_sql(args: argparse.Namespace) -> str:
    embedding = embed_text(args.question, args.dimensions, args.embedding_provider)
    embedding_json = json.dumps(embedding, ensure_ascii=False, separators=(",", ":"))

    return "\n".join(
        [
            "PRINT 'hybrid_search_query.sql';",
            "GO",
            f"DECLARE @Question nvarchar(max) = {sql_string(args.question)};",
            f"DECLARE @QuestionEmbeddingJson nvarchar(max) = {sql_string(embedding_json)};",
            "",
            "EXEC rag.usp_get_hybrid_candidate_chunks",
            f"    @returnCaseId = {sql_string(args.return_case_id, unicode=False)},",
            "    @question = @Question,",
            "    @questionEmbeddingJson = @QuestionEmbeddingJson,",
            f"    @embeddingModel = {sql_string(args.resolved_embedding_model)},",
            f"    @topN = {args.top_n},",
            f"    @lexicalWeight = {args.lexical_weight:.4f},",
            f"    @vectorWeight = {args.vector_weight:.4f};",
            "GO",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Render SQL for hybrid RAG search.")
    parser.add_argument("--out", type=Path, default=Path("database/generated/hybrid_search_query.sql"))
    parser.add_argument("--return-case-id", default="RET-2026-004219")
    parser.add_argument("--question", default=DEFAULT_QUESTION)
    parser.add_argument("--dimensions", type=int, default=int(os.getenv("RAG_EMBEDDING_DIMENSIONS", "64")))
    parser.add_argument("--embedding-provider", choices=["demo", "azure-openai"], default=os.getenv("RAG_EMBEDDING_PROVIDER"))
    parser.add_argument("--embedding-model", default=None)
    parser.add_argument("--top-n", type=int, default=8)
    parser.add_argument("--lexical-weight", type=float, default=float(os.getenv("RAG_HYBRID_LEXICAL_WEIGHT", "0.55")))
    parser.add_argument("--vector-weight", type=float, default=float(os.getenv("RAG_HYBRID_VECTOR_WEIGHT", "0.45")))
    args = parser.parse_args()

    if args.top_n < 1:
        raise ValueError("--top-n debe ser mayor que cero.")
    if args.lexical_weight < 0 or args.vector_weight < 0:
        raise ValueError("Los pesos no pueden ser negativos.")
    if args.lexical_weight == 0 and args.vector_weight == 0:
        raise ValueError("Al menos uno de los pesos debe ser mayor que cero.")

    args.resolved_embedding_model = args.embedding_model or resolve_embedding_model(
        "demo-hash-embedding-v1",
        args.embedding_provider,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render_sql(args), encoding="utf-8")
    print(f"SQL híbrido generado: {args.out}")


if __name__ == "__main__":
    main()
