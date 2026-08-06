import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List

import fabric.functions as fn

udf = fn.UserDataFunctions()
SQL_ALIAS = 'frasohomesql'
MODEL_NAME = "frasohome-rag-rulebased-v1"


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime,)):
        return value.isoformat()
    return str(value)


def _rows_to_dicts(cursor) -> List[Dict[str, Any]]:
    if cursor.description is None:
        return []
    columns = [col[0] for col in cursor.description]
    rows = []
    for row in cursor.fetchall():
        rows.append({columns[i]: row[i] for i in range(len(columns))})
    return rows


def _first_row(cursor) -> Dict[str, Any]:
    rows = _rows_to_dicts(cursor)
    return rows[0] if rows else {}


def _execute_context(conn, return_case_id: str) -> Dict[str, Any]:
    cursor = conn.cursor()
    cursor.execute("EXEC rag.usp_get_return_case_context ?", return_case_id)
    return _first_row(cursor)


def _execute_chunks(conn, return_case_id: str, question: str, max_chunks: int) -> List[Dict[str, Any]]:
    cursor = conn.cursor()
    cursor.execute("EXEC rag.usp_get_candidate_chunks ?, ?, ?", return_case_id, question, max_chunks)
    return _rows_to_dicts(cursor)


def _build_recommendation(context: Dict[str, Any], chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
    segment = str(context.get("Segment", "")).lower()
    reason = str(context.get("ReasonText", "")).lower()
    desired = str(context.get("DesiredOutcome", "")).lower()
    category = str(context.get("Category", "")).lower()
    risk = float(context.get("ReturnRiskScore") or 1.0)
    has_photos = bool(context.get("HasPhotos"))
    is_bulky = bool(context.get("IsBulky"))
    is_custom = bool(context.get("IsCustomMade"))
    replaceable_units = int(context.get("ReplaceableUnits") or 0)
    days_since_delivery = int(context.get("DaysSinceDelivery") or 999)

    damage_signal = any(token in reason for token in ["dañ", "golpe", "rota", "rotura", "embalaje"])
    vip_signal = segment in {"gold", "platinum"}
    stock_signal = replaceable_units > 0

    reasons: List[str] = []
    actions: List[str] = []
    requires_manual_review = False
    confidence = 0.55

    if is_custom and not damage_signal:
        recommendation = "Revisión manual por producto personalizado"
        reasons.append("El producto es personalizado y la solicitud no indica daño de transporte.")
        actions.append("Escalar a revisión manual por excepción de producto a medida.")
        requires_manual_review = True
        confidence = 0.72
    elif damage_signal and has_photos and stock_signal and not is_custom:
        recommendation = "Aprobar reemplazo prioritario condicionado a validación visual"
        reasons.append("La reclamación indica daño de transporte o embalaje golpeado.")
        reasons.append("El cliente aporta evidencia fotográfica.")
        reasons.append("Hay unidades reemplazables disponibles por encima del stock de seguridad.")
        confidence = 0.84
        if is_bulky or category == "furniture":
            reasons.append("El producto es voluminoso y requiere recogida coordinada.")
            actions.append("Crear orden de recogida sin coste condicionada a revisión visual.")
        if vip_signal and risk < 0.20:
            reasons.append("El cliente es Gold/Platinum y tiene bajo riesgo de devolución.")
            actions.append("Priorizar la reserva de reemplazo y la ventana de recogida.")
            confidence += 0.06
        actions.append("Reservar unidad de reemplazo en el almacén con disponibilidad.")
        actions.append("Solicitar validación visual de las fotografías antes de cerrar el caso.")
    elif damage_signal and not has_photos:
        recommendation = "Solicitar evidencia antes de aprobar"
        reasons.append("La reclamación menciona daño, pero no consta evidencia fotográfica.")
        actions.append("Solicitar fotos del embalaje y del producto.")
        requires_manual_review = True
        confidence = 0.70
    elif desired == "refund":
        recommendation = "Evaluar devolución estándar"
        reasons.append("La solicitud parece una devolución estándar por preferencia del cliente.")
        if days_since_delivery > 30:
            reasons.append("La solicitud supera 30 días desde la entrega; verificar política vigente por canal.")
            requires_manual_review = True
        actions.append("Validar plazo de devolución, estado del artículo y excepciones por categoría.")
        confidence = 0.64
    else:
        recommendation = "Revisión manual"
        reasons.append("No hay señales suficientes para una aprobación automática.")
        actions.append("Escalar al supervisor con los documentos recuperados.")
        requires_manual_review = True
        confidence = 0.58

    evidence = []
    seen_codes = set()
    for chunk in chunks:
        code = chunk.get("DocumentCode")
        if code and code not in seen_codes:
            seen_codes.add(code)
            evidence.append(
                {
                    "documentCode": code,
                    "documentTitle": chunk.get("DocumentTitle"),
                    "chunkNumber": chunk.get("ChunkNumber"),
                    "score": float(chunk.get("Score") or 0),
                    "excerpt": str(chunk.get("ChunkText", ""))[:260],
                }
            )

    return {
        "recommendation": recommendation,
        "confidence": round(min(confidence, 0.95), 4),
        "requiresManualReview": requires_manual_review,
        "reasons": reasons,
        "nextActions": actions,
        "evidence": evidence,
    }


def _write_audit(conn, return_case_id: str, question: str, answer: Dict[str, Any], chunks: List[Dict[str, Any]]) -> int:
    cited_documents = ",".join([e["documentCode"] for e in answer.get("evidence", [])])
    answer_json = json.dumps(answer, ensure_ascii=False, default=_json_default)
    retrieval_json = json.dumps(
        {
            "retrievedAtUtc": datetime.now(timezone.utc).isoformat(),
            "chunks": chunks,
        },
        ensure_ascii=False,
        default=_json_default,
    )
    cursor = conn.cursor()
    cursor.execute(
        "EXEC rag.usp_insert_answer_audit ?, ?, ?, ?, ?, ?, ?, ?",
        return_case_id,
        question,
        answer["recommendation"],
        answer["confidence"],
        answer_json,
        cited_documents,
        retrieval_json,
        MODEL_NAME,
    )
    row = cursor.fetchone()
    conn.commit()
    return int(row[0]) if row else -1


@udf.function()
def healthCheck() -> dict:
    """Public lightweight health check."""
    logging.info("healthCheck invoked")
    return {
        "status": "ok",
        "service": "FrasoHome_RAG_UDF",
        "modelName": MODEL_NAME,
        "utc": datetime.now(timezone.utc).isoformat(),
    }


@udf.connection(argName="sqlDB", alias=SQL_ALIAS)
@udf.function()
def getReturnCaseContext(sqlDB: fn.FabricSqlConnection, returnCaseId: str) -> dict:
    """Return operational context for a return case."""
    logging.info("getReturnCaseContext invoked for %s", returnCaseId)
    conn = sqlDB.connect()
    context = _execute_context(conn, returnCaseId)
    if not context:
        return {"found": False, "returnCaseId": returnCaseId}
    return {"found": True, "context": context}


@udf.connection(argName="sqlDB", alias=SQL_ALIAS)
@udf.function()
def answerReturnCase(sqlDB: fn.FabricSqlConnection, returnCaseId: str, question: str, maxChunks: int = 6) -> dict:
    """
    Orquesta la demo RAG FraSoHome.

    Parámetros en camelCase para compatibilidad con User Data Functions.
    """
    logging.info("answerReturnCase invoked for %s", returnCaseId)
    if not returnCaseId:
        raise ValueError("returnCaseId is required")
    if not question:
        raise ValueError("question is required")
    if maxChunks < 1 or maxChunks > 20:
        maxChunks = 6

    conn = sqlDB.connect()
    context = _execute_context(conn, returnCaseId)
    if not context:
        return {
            "returnCaseId": returnCaseId,
            "question": question,
            "recommendation": "Caso no encontrado",
            "confidence": 0.0,
            "requiresManualReview": True,
            "reasons": ["No se encontró el caso de devolución en SQL Database."],
            "nextActions": ["Verificar el identificador del caso."],
            "evidence": [],
        }

    chunks = _execute_chunks(conn, returnCaseId, question, maxChunks)
    answer = _build_recommendation(context, chunks)
    answer["returnCaseId"] = returnCaseId
    answer["question"] = question
    answer["operationalContext"] = context
    answer["retrievedChunks"] = chunks
    answer["modelName"] = MODEL_NAME
    answer["generatedAtUtc"] = datetime.now(timezone.utc).isoformat()
    answer["auditId"] = _write_audit(conn, returnCaseId, question, answer, chunks)
    return answer
