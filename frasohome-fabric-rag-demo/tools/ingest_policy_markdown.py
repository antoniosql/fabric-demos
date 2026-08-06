#!/usr/bin/env python3
"""
Genera un script SQL de ingesta RAG a partir de politicas Markdown.

El flujo evita dependencias nuevas: lee documentos Markdown con frontmatter simple,
crea chunks por secciones/parrafos, calcula embeddings deterministas de demo y
emite SQL idempotente para rag.Documents, rag.Chunks y rag.ChunkEmbeddings.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

from seed_embeddings import embed_text, resolve_embedding_model


DEFAULT_SOURCE_DIR = Path("docs/policies")
DEFAULT_OUT = Path("database/generated/ingest_policy_markdown.sql")
DEFAULT_EMBEDDING_MODEL = "demo-hash-embedding-v1"
DEFAULT_QUESTION = (
    "El cliente Gold quiere devolver un sofá modular comprado online hace 34 días. "
    "Indica que llegó con una pata dañada, conserva fotos del embalaje y solicita reemplazo urgente."
)


@dataclass
class Document:
    code: str
    title: str
    document_type: str
    valid_from: str
    valid_to: str | None
    security_level: str
    source_uri: str
    content: str
    product_category: str
    channel: str
    country_code: str
    keywords: str
    path: Path


@dataclass
class Chunk:
    document: Document
    number: int
    text: str
    product_category: str
    channel: str
    country_code: str
    keywords: str
    embedding: List[float]


def parse_frontmatter(raw: str) -> tuple[dict[str, str], str]:
    if not raw.startswith("---"):
        return {}, raw.strip()

    parts = raw.split("---", 2)
    if len(parts) < 3:
        return {}, raw.strip()

    metadata: dict[str, str] = {}
    for line in parts[1].splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, separator, value = line.partition(":")
        if not separator:
            continue
        metadata[key.strip().lower()] = value.strip().strip('"').strip("'")

    return metadata, parts[2].strip()


def required(metadata: dict[str, str], key: str, path: Path) -> str:
    value = metadata.get(key, "").strip()
    if not value:
        raise ValueError(f"{path}: falta el campo obligatorio '{key}' en el frontmatter.")
    return value


def load_document(path: Path) -> Document:
    raw = path.read_text(encoding="utf-8")
    metadata, content = parse_frontmatter(raw)

    return Document(
        code=required(metadata, "document_code", path),
        title=required(metadata, "document_title", path),
        document_type=metadata.get("document_type", "policy") or "policy",
        valid_from=metadata.get("valid_from", "2026-01-01") or "2026-01-01",
        valid_to=metadata.get("valid_to") or None,
        security_level=metadata.get("security_level", "internal") or "internal",
        source_uri=metadata.get("source_uri", path.as_posix()) or path.as_posix(),
        content=content,
        product_category=metadata.get("product_category", "all") or "all",
        channel=metadata.get("channel", "all") or "all",
        country_code=metadata.get("country_code", "ES") or "ES",
        keywords=metadata.get("keywords", ""),
        path=path,
    )


def markdown_to_plain_text(text: str) -> str:
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def split_sections(content: str) -> list[str]:
    lines = content.splitlines()
    sections: list[list[str]] = []
    current: list[str] = []

    for line in lines:
        if re.match(r"^#{1,6}\s+", line) and current:
            sections.append(current)
            current = [line]
        else:
            current.append(line)

    if current:
        sections.append(current)

    return ["\n".join(section).strip() for section in sections if "\n".join(section).strip()]


def split_long_section(section: str, max_chars: int) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", section) if p.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_length = 0

    for paragraph in paragraphs:
        plain = markdown_to_plain_text(paragraph)
        candidate_length = current_length + len(plain) + 2
        if current and candidate_length > max_chars:
            chunks.append("\n\n".join(current))
            current = [paragraph]
            current_length = len(plain)
        else:
            current.append(paragraph)
            current_length = candidate_length

    if current:
        chunks.append("\n\n".join(current))

    return chunks


def infer_keywords(text: str, base_keywords: str) -> str:
    vocabulary = [
        "daño",
        "transporte",
        "evidencia",
        "fotográfica",
        "embalaje",
        "reemplazo",
        "reembolso",
        "mueble",
        "voluminoso",
        "stock",
        "seguridad",
        "Gold",
        "Platinum",
        "riesgo",
        "recogida",
        "revisión",
        "visual",
        "ecommerce",
    ]
    lowered = text.lower()
    found = []
    for term in vocabulary:
        if term.lower() in lowered:
            found.append(term)

    combined = [k.strip() for k in base_keywords.split() if k.strip()] + found
    unique: list[str] = []
    seen: set[str] = set()
    for keyword in combined:
        key = keyword.lower()
        if key not in seen:
            seen.add(key)
            unique.append(keyword)
    return " ".join(unique[:30])


def chunk_document(document: Document, max_chars: int, dimensions: int, embedding_provider: str) -> list[Chunk]:
    chunks: list[Chunk] = []
    for section in split_sections(document.content):
        for part in split_long_section(section, max_chars):
            plain_text = markdown_to_plain_text(part)
            if not plain_text:
                continue
            chunks.append(
                Chunk(
                    document=document,
                    number=len(chunks) + 1,
                    text=plain_text,
                    product_category=document.product_category,
                    channel=document.channel,
                    country_code=document.country_code,
                    keywords=infer_keywords(plain_text, document.keywords),
                    embedding=embed_text(plain_text, dimensions, embedding_provider),
                )
            )
    return chunks


def sql_string(value: str | None, unicode: bool = True) -> str:
    if value is None or value == "":
        return "NULL"
    prefix = "N" if unicode else ""
    return f"{prefix}'{value.replace(chr(39), chr(39) + chr(39))}'"


def sql_date(value: str | None) -> str:
    if not value:
        return "NULL"
    return f"CONVERT(date, '{value}', 23)"


def render_sql(documents: list[Document], chunks_by_document: dict[str, list[Chunk]], embedding_model: str) -> str:
    lines = [
        "PRINT 'ingest_policy_markdown.sql';",
        "GO",
        "SET XACT_ABORT ON;",
        "BEGIN TRANSACTION;",
        "DECLARE @DocumentId int;",
        "DECLARE @ChunkId bigint;",
        "",
    ]

    for document in documents:
        lines.extend(
            [
                f"PRINT 'Ingesting {document.code}';",
                "MERGE rag.Documents AS target",
                "USING (SELECT",
                f"    DocumentCode = {sql_string(document.code, unicode=False)},",
                f"    DocumentTitle = {sql_string(document.title)},",
                f"    DocumentType = {sql_string(document.document_type, unicode=False)},",
                f"    ValidFrom = {sql_date(document.valid_from)},",
                f"    ValidTo = {sql_date(document.valid_to)},",
                f"    SecurityLevel = {sql_string(document.security_level, unicode=False)},",
                f"    SourceUri = {sql_string(document.source_uri)},",
                f"    Content = {sql_string(document.content)}",
                ") AS source",
                "ON target.DocumentCode = source.DocumentCode",
                "WHEN MATCHED THEN UPDATE SET",
                "    DocumentTitle = source.DocumentTitle,",
                "    DocumentType = source.DocumentType,",
                "    ValidFrom = source.ValidFrom,",
                "    ValidTo = source.ValidTo,",
                "    SecurityLevel = source.SecurityLevel,",
                "    SourceUri = source.SourceUri,",
                "    Content = source.Content",
                "WHEN NOT MATCHED THEN INSERT(DocumentCode, DocumentTitle, DocumentType, ValidFrom, ValidTo, SecurityLevel, SourceUri, Content)",
                "VALUES(source.DocumentCode, source.DocumentTitle, source.DocumentType, source.ValidFrom, source.ValidTo, source.SecurityLevel, source.SourceUri, source.Content);",
                "",
                f"SET @DocumentId = (SELECT DocumentId FROM rag.Documents WHERE DocumentCode = {sql_string(document.code, unicode=False)});",
                "DELETE e",
                "FROM rag.ChunkEmbeddings AS e",
                "JOIN rag.Chunks AS c ON c.ChunkId = e.ChunkId",
                "WHERE c.DocumentId = @DocumentId;",
                "DELETE FROM rag.Chunks WHERE DocumentId = @DocumentId;",
                "",
            ]
        )

        for chunk in chunks_by_document[document.code]:
            embedding_json = json.dumps(chunk.embedding, ensure_ascii=False, separators=(",", ":"))
            lines.extend(
                [
                    "INSERT INTO rag.Chunks",
                    "(",
                    "    DocumentId, ChunkNumber, ChunkText, ProductCategory, Channel, CountryCode,",
                    "    ValidFrom, ValidTo, Keywords",
                    ")",
                    "VALUES",
                    "(",
                    f"    @DocumentId, {chunk.number}, {sql_string(chunk.text)},",
                    f"    {sql_string(chunk.product_category, unicode=False)}, {sql_string(chunk.channel, unicode=False)}, {sql_string(chunk.country_code, unicode=False)},",
                    f"    {sql_date(document.valid_from)}, {sql_date(document.valid_to)}, {sql_string(chunk.keywords)}",
                    ");",
                    "SET @ChunkId = CONVERT(bigint, SCOPE_IDENTITY());",
                    "INSERT INTO rag.ChunkEmbeddings(ChunkId, EmbeddingModel, EmbeddingDimensions, EmbeddingJson)",
                    "VALUES",
                    "(",
                    f"    @ChunkId, {sql_string(embedding_model)}, {len(chunk.embedding)}, {sql_string(embedding_json)}",
                    ");",
                    "",
                ]
            )

    lines.extend(["COMMIT TRANSACTION;", "GO", ""])
    return "\n".join(lines)


def load_all_documents(source_dir: Path) -> list[Document]:
    paths = sorted(source_dir.glob("*.md"))
    if not paths:
        raise ValueError(f"No se encontraron documentos Markdown en {source_dir}.")
    return [load_document(path) for path in paths]


def score_preview(chunk: Chunk, question: str) -> float:
    q = question.lower()
    text = f"{chunk.text} {chunk.keywords}".lower()
    score = 0.0
    score += 0.50 if chunk.country_code in {"ES", "all"} else 0
    score += 1.00 if chunk.channel in {"ecommerce", "all"} else 0
    score += 1.00 if chunk.product_category in {"furniture", "all"} else 0
    score += 3.00 if any(t in q for t in ["dañ", "rota", "golpe"]) and "daño" in text else 0
    score += 2.50 if "embalaje" in q and "embalaje" in text else 0
    score += 2.00 if any(t in q for t in ["foto", "fotográfica"]) and ("fotográfica" in text or "evidencia" in text) else 0
    score += 2.00 if any(t in q for t in ["reemplazo", "sustitución"]) and "reemplazo" in text else 0
    score += 2.25 if "voluminoso" in text else 0
    score += 2.25 if any(t in q for t in ["gold", "platinum"]) and ("gold" in text or "platinum" in text) else 0
    score += 1.50 if "stock" in q and "stock" in text else 0
    return score


def print_preview(chunks: Iterable[Chunk], question: str) -> None:
    ranked = sorted(((score_preview(chunk, question), chunk) for chunk in chunks), key=lambda item: item[0], reverse=True)
    print("Preview de recuperación local:")
    for score, chunk in ranked[:8]:
        print(f"- {chunk.document.code} chunk {chunk.number}: score={score:.2f} :: {chunk.text[:120]}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingesta Markdown -> chunks -> embeddings -> SQL.")
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--max-chars", type=int, default=900)
    parser.add_argument("--dimensions", type=int, default=int(os.getenv("RAG_EMBEDDING_DIMENSIONS", "64")))
    parser.add_argument("--embedding-provider", choices=["demo", "azure-openai"], default=os.getenv("RAG_EMBEDDING_PROVIDER"))
    parser.add_argument("--embedding-model", default=None)
    parser.add_argument("--preview-question", default=DEFAULT_QUESTION)
    parser.add_argument("--no-preview", action="store_true")
    args = parser.parse_args()

    embedding_model = args.embedding_model or resolve_embedding_model(DEFAULT_EMBEDDING_MODEL, args.embedding_provider)
    documents = load_all_documents(args.source_dir)
    chunks_by_document = {
        document.code: chunk_document(document, args.max_chars, args.dimensions, args.embedding_provider)
        for document in documents
    }
    all_chunks = [chunk for chunks in chunks_by_document.values() for chunk in chunks]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render_sql(documents, chunks_by_document, embedding_model), encoding="utf-8")

    print(f"Documentos leídos: {len(documents)}")
    print(f"Chunks generados: {len(all_chunks)}")
    print(f"SQL generado: {args.out}")
    if not args.no_preview:
        print_preview(all_chunks, args.preview_question)


if __name__ == "__main__":
    main()
