PRINT '99_smoke_test.sql';
GO

EXEC rag.usp_get_return_case_context 'RET-2026-004219';
GO

EXEC rag.usp_get_candidate_chunks
    @returnCaseId = 'RET-2026-004219',
    @question = N'El cliente quiere devolver un sofá modular comprado online hace 34 días. Indica que llegó con una pata dañada, conserva fotos del embalaje y solicita reemplazo urgente. ¿Debemos aprobar devolución, reemplazo o revisión manual?',
    @topN = 5;
GO

SELECT TOP 5
    d.DocumentCode,
    d.DocumentTitle,
    c.ChunkNumber,
    c.ChunkText
FROM rag.Chunks AS c
JOIN rag.Documents AS d
    ON d.DocumentId = c.DocumentId
ORDER BY d.DocumentCode, c.ChunkNumber;
GO
