PRINT '07_create_hybrid_search.sql';
GO

CREATE OR ALTER PROCEDURE rag.usp_get_hybrid_candidate_chunks
    @returnCaseId varchar(30),
    @question nvarchar(max),
    @questionEmbeddingJson nvarchar(max),
    @embeddingModel nvarchar(120) = N'demo-hash-embedding-v1',
    @topN int = 6,
    @lexicalWeight decimal(5,4) = 0.5500,
    @vectorWeight decimal(5,4) = 0.4500
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE
        @category varchar(80),
        @channel varchar(40),
        @openedDate date,
        @q nvarchar(max),
        @reason nvarchar(max),
        @hasPhotos bit,
        @isBulky bit,
        @questionNorm float;

    SELECT
        @category = p.Category,
        @channel = o.Channel,
        @openedDate = CAST(rc.OpenedAt AS date),
        @reason = rc.ReasonText,
        @hasPhotos = rc.HasPhotos,
        @isBulky = p.IsBulky
    FROM fraso.ReturnCases AS rc
    JOIN fraso.Orders AS o ON o.OrderId = rc.OrderId
    JOIN fraso.Products AS p ON p.ProductId = rc.ProductId
    WHERE rc.ReturnCaseId = @returnCaseId;

    SET @q = LOWER(CONCAT(@question, N' ', @reason));

    DECLARE @QuestionVector TABLE
    (
        VectorIndex int NOT NULL PRIMARY KEY,
        VectorValue float NOT NULL
    );

    INSERT INTO @QuestionVector(VectorIndex, VectorValue)
    SELECT
        TRY_CONVERT(int, [key]) AS VectorIndex,
        TRY_CONVERT(float, value) AS VectorValue
    FROM OPENJSON(@questionEmbeddingJson)
    WHERE TRY_CONVERT(int, [key]) IS NOT NULL
      AND TRY_CONVERT(float, value) IS NOT NULL;

    SELECT @questionNorm = SQRT(SUM(VectorValue * VectorValue))
    FROM @QuestionVector;

    IF @questionNorm IS NULL OR @questionNorm = 0
    BEGIN
        SET @questionNorm = 1;
    END;

    ;WITH Candidate AS
    (
        SELECT
            c.ChunkId,
            d.DocumentCode,
            d.DocumentTitle,
            d.DocumentType,
            d.SecurityLevel,
            c.ChunkNumber,
            c.ChunkText,
            c.ProductCategory,
            c.Channel,
            c.CountryCode,
            c.Keywords,
            LexicalScore =
                CAST(0 AS decimal(9,4))
                + CASE WHEN c.CountryCode IN ('ES', 'all') THEN 0.50 ELSE 0 END
                + CASE WHEN c.Channel IN (@channel, 'all') THEN 1.00 ELSE 0 END
                + CASE WHEN c.ProductCategory IN (@category, 'all') THEN 1.00 ELSE 0 END
                + CASE WHEN @q LIKE N'%dañ%' OR @q LIKE N'%rota%' OR @q LIKE N'%golpe%' THEN CASE WHEN c.ChunkText LIKE N'%daño%' OR c.Keywords LIKE N'%daño%' THEN 3.00 ELSE 0 END ELSE 0 END
                + CASE WHEN @q LIKE N'%embalaje%' THEN CASE WHEN c.ChunkText LIKE N'%embalaje%' OR c.Keywords LIKE N'%embalaje%' THEN 2.50 ELSE 0 END ELSE 0 END
                + CASE WHEN @q LIKE N'%foto%' OR @hasPhotos = 1 THEN CASE WHEN c.ChunkText LIKE N'%fotográfica%' OR c.ChunkText LIKE N'%evidencia%' OR c.Keywords LIKE N'%evidencia%' THEN 2.00 ELSE 0 END ELSE 0 END
                + CASE WHEN @q LIKE N'%reemplazo%' OR @q LIKE N'%sustitución%' THEN CASE WHEN c.ChunkText LIKE N'%reemplazo%' OR c.Keywords LIKE N'%reemplazo%' THEN 2.00 ELSE 0 END ELSE 0 END
                + CASE WHEN @isBulky = 1 THEN CASE WHEN c.ChunkText LIKE N'%voluminoso%' OR c.Keywords LIKE N'%voluminoso%' THEN 2.25 ELSE 0 END ELSE 0 END
                + CASE WHEN @q LIKE N'%gold%' OR @q LIKE N'%platinum%' THEN CASE WHEN c.ChunkText LIKE N'%Gold%' OR c.ChunkText LIKE N'%Platinum%' THEN 2.25 ELSE 0 END ELSE 0 END
                + CASE WHEN @q LIKE N'%stock%' THEN CASE WHEN c.ChunkText LIKE N'%stock%' OR c.Keywords LIKE N'%stock%' THEN 1.50 ELSE 0 END ELSE 0 END,
            ce.EmbeddingJson
        FROM rag.Chunks AS c
        JOIN rag.Documents AS d
            ON d.DocumentId = c.DocumentId
        LEFT JOIN rag.ChunkEmbeddings AS ce
            ON ce.ChunkId = c.ChunkId
           AND ce.EmbeddingModel = @embeddingModel
        WHERE c.ValidFrom <= @openedDate
          AND (c.ValidTo IS NULL OR c.ValidTo >= @openedDate)
          AND (c.CountryCode IN ('ES', 'all') OR c.CountryCode IS NULL)
          AND (c.Channel IN (@channel, 'all') OR c.Channel IS NULL)
          AND (c.ProductCategory IN (@category, 'all') OR c.ProductCategory IS NULL)
    ),
    VectorRaw AS
    (
        SELECT
            c.ChunkId,
            DotProduct = SUM(qv.VectorValue * TRY_CONVERT(float, ev.value)),
            ChunkNorm = SQRT(SUM(TRY_CONVERT(float, ev.value) * TRY_CONVERT(float, ev.value)))
        FROM Candidate AS c
        CROSS APPLY OPENJSON(c.EmbeddingJson) AS ev
        JOIN @QuestionVector AS qv
            ON qv.VectorIndex = TRY_CONVERT(int, ev.[key])
        WHERE c.EmbeddingJson IS NOT NULL
          AND TRY_CONVERT(float, ev.value) IS NOT NULL
        GROUP BY c.ChunkId
    ),
    Scored AS
    (
        SELECT
            c.ChunkId,
            c.DocumentCode,
            c.DocumentTitle,
            c.DocumentType,
            c.SecurityLevel,
            c.ChunkNumber,
            c.ChunkText,
            c.ProductCategory,
            c.Channel,
            c.CountryCode,
            c.Keywords,
            c.LexicalScore,
            LexicalNormalized =
                CAST(
                    CASE
                        WHEN MAX(c.LexicalScore) OVER () > 0
                        THEN c.LexicalScore / MAX(c.LexicalScore) OVER ()
                        ELSE 0
                    END
                    AS decimal(9,6)
                ),
            VectorScore =
                CAST(
                    CASE
                        WHEN vr.ChunkNorm IS NOT NULL AND vr.ChunkNorm > 0
                        THEN (COALESCE(vr.DotProduct, 0) / (@questionNorm * vr.ChunkNorm) + 1.0) / 2.0
                        ELSE 0
                    END
                    AS decimal(9,6)
                )
        FROM Candidate AS c
        LEFT JOIN VectorRaw AS vr
            ON vr.ChunkId = c.ChunkId
        WHERE c.LexicalScore > 0 OR vr.ChunkId IS NOT NULL
    ),
    Hybrid AS
    (
        SELECT
            ChunkId,
            DocumentCode,
            DocumentTitle,
            DocumentType,
            SecurityLevel,
            ChunkNumber,
            ChunkText,
            ProductCategory,
            Channel,
            CountryCode,
            Keywords,
            LexicalScore,
            LexicalNormalized,
            VectorScore,
            HybridScore =
                CAST((@lexicalWeight * LexicalNormalized) + (@vectorWeight * VectorScore) AS decimal(9,6))
        FROM Scored
    )
    SELECT TOP (@topN)
        ChunkId,
        DocumentCode,
        DocumentTitle,
        DocumentType,
        SecurityLevel,
        ChunkNumber,
        ChunkText,
        ProductCategory,
        Channel,
        CountryCode,
        Keywords,
        Score = HybridScore,
        LexicalScore,
        LexicalNormalized,
        VectorScore,
        HybridScore
    FROM Hybrid
    ORDER BY HybridScore DESC, VectorScore DESC, LexicalScore DESC, DocumentCode, ChunkNumber;
END;
GO
