PRINT '98_smoke_test_markdown_ingestion.sql';
GO

DECLARE @Question nvarchar(max) =
    N'El cliente Gold quiere devolver un sofá modular comprado online hace 34 días. Indica que llegó con una pata dañada, conserva fotos del embalaje y solicita reemplazo urgente. ¿Debemos aprobar devolución, reemplazo o revisión manual?';

DECLARE @Candidates TABLE
(
    ChunkId bigint,
    DocumentCode varchar(50),
    DocumentTitle nvarchar(200),
    DocumentType varchar(50),
    SecurityLevel varchar(30),
    ChunkNumber int,
    ChunkText nvarchar(max),
    ProductCategory varchar(80),
    Channel varchar(40),
    CountryCode varchar(10),
    Keywords nvarchar(400),
    Score decimal(9,4)
);

INSERT INTO @Candidates
EXEC rag.usp_get_candidate_chunks
    @returnCaseId = 'RET-2026-004219',
    @question = @Question,
    @topN = 12;

IF NOT EXISTS (SELECT 1 FROM @Candidates WHERE DocumentCode = 'MD-POL-DMG-010')
BEGIN
    THROW 51000, 'No se recuperó el documento Markdown MD-POL-DMG-010.', 1;
END;

IF NOT EXISTS (SELECT 1 FROM @Candidates WHERE DocumentCode = 'MD-POL-VIP-011')
BEGIN
    THROW 51001, 'No se recuperó el documento Markdown MD-POL-VIP-011.', 1;
END;

SELECT
    DocumentCode,
    DocumentTitle,
    ChunkNumber,
    Score,
    LEFT(ChunkText, 220) AS ChunkPreview
FROM @Candidates
WHERE DocumentCode LIKE 'MD-POL-%'
ORDER BY Score DESC, DocumentCode, ChunkNumber;

SELECT
    ExpectedRecommendation = N'Aprobar reemplazo prioritario condicionado a validación visual',
    Why = N'Los chunks Markdown recuperados contienen daño de transporte, evidencia fotográfica, embalaje, stock, mueble voluminoso y cliente Gold.';
GO
