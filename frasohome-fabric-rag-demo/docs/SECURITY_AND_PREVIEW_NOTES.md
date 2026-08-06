# Seguridad, gobierno y notas de preview

## Seguridad

- No exponer claves ni secretos en el frontend.
- Usar Microsoft Entra para autenticar llamadas a endpoints UDF.
- Usar conexiones Fabric administradas para que la UDF acceda a SQL sin connection strings en código.
- Aplicar permisos SQL por rol y `GRANT EXECUTE` a procedimientos en lugar de acceso directo a tablas.
- Registrar auditoría de preguntas, chunks recuperados, recomendación y modelo usado.

## Gobierno RAG

Buenas prácticas incluidas:

- Citas obligatorias.
- Filtros por vigencia, país, canal y categoría.
- Respuesta con `confidence` y `requiresManualReview`.
- Auditoría en `rag.AnswerAudit`.
- Fallback cuando el contexto no es suficiente.

## Funcionalidades preview

Fabric Apps, User Data Functions y capacidades vectoriales SQL pueden estar en preview o tener disponibilidad regional/tenant. Por eso el repositorio incluye:

- Camino principal robusto basado en T-SQL y Python.
- Script opcional de `vector` para tenants que ya tengan la funcionalidad.
- Pasos manuales claros para URL pública UDF y app registration.
