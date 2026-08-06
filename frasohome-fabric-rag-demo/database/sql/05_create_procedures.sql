PRINT '05_create_procedures.sql';
GO

CREATE OR ALTER PROCEDURE rag.usp_get_return_case_context
    @returnCaseId varchar(30)
AS
BEGIN
    SET NOCOUNT ON;

    SELECT
        rc.ReturnCaseId,
        rc.OpenedAt,
        rc.ReasonText,
        rc.HasPhotos,
        rc.DesiredOutcome,
        rc.Status AS ReturnCaseStatus,
        c.CustomerId,
        c.CustomerName,
        c.Segment,
        c.ReturnRiskScore,
        c.City,
        o.OrderId,
        o.OrderDate,
        o.DeliveryDate,
        DATEDIFF(day, o.DeliveryDate, CAST(rc.OpenedAt AS date)) AS DaysSinceDelivery,
        o.Channel,
        o.TotalAmount,
        p.ProductId,
        p.ProductName,
        p.Category,
        p.Subcategory,
        p.IsBulky,
        p.IsCustomMade,
        p.WarrantyMonths,
        COALESCE(SUM(CASE WHEN s.AvailableUnits > s.SafetyStock THEN s.AvailableUnits - s.SafetyStock ELSE 0 END), 0) AS ReplaceableUnits,
        STRING_AGG(CONCAT(s.LocationCode, ': ', s.LocationName, ' (', s.AvailableUnits, ')'), '; ') AS StockLocations
    FROM fraso.ReturnCases AS rc
    JOIN fraso.Customers AS c
        ON c.CustomerId = rc.CustomerId
    JOIN fraso.Orders AS o
        ON o.OrderId = rc.OrderId
    JOIN fraso.Products AS p
        ON p.ProductId = rc.ProductId
    LEFT JOIN fraso.Stock AS s
        ON s.ProductId = rc.ProductId
    WHERE rc.ReturnCaseId = @returnCaseId
    GROUP BY
        rc.ReturnCaseId, rc.OpenedAt, rc.ReasonText, rc.HasPhotos, rc.DesiredOutcome, rc.Status,
        c.CustomerId, c.CustomerName, c.Segment, c.ReturnRiskScore, c.City,
        o.OrderId, o.OrderDate, o.DeliveryDate, o.Channel, o.TotalAmount,
        p.ProductId, p.ProductName, p.Category, p.Subcategory, p.IsBulky, p.IsCustomMade, p.WarrantyMonths;
END;
GO

CREATE OR ALTER PROCEDURE rag.usp_get_candidate_chunks
    @returnCaseId varchar(30),
    @question nvarchar(max),
    @topN int = 6
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
        @isBulky bit;

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
            Score =
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
                + CASE WHEN @q LIKE N'%stock%' THEN CASE WHEN c.ChunkText LIKE N'%stock%' OR c.Keywords LIKE N'%stock%' THEN 1.50 ELSE 0 END ELSE 0 END
        FROM rag.Chunks AS c
        JOIN rag.Documents AS d
            ON d.DocumentId = c.DocumentId
        WHERE c.ValidFrom <= @openedDate
          AND (c.ValidTo IS NULL OR c.ValidTo >= @openedDate)
          AND (c.CountryCode IN ('ES', 'all') OR c.CountryCode IS NULL)
          AND (c.Channel IN (@channel, 'all') OR c.Channel IS NULL)
          AND (c.ProductCategory IN (@category, 'all') OR c.ProductCategory IS NULL)
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
        Score
    FROM Candidate
    WHERE Score > 0
    ORDER BY Score DESC, DocumentCode, ChunkNumber;
END;
GO

CREATE OR ALTER PROCEDURE rag.usp_insert_answer_audit
    @returnCaseId varchar(30),
    @userQuestion nvarchar(max),
    @recommendation nvarchar(200),
    @confidence decimal(5,4),
    @answerJson nvarchar(max),
    @citedDocuments nvarchar(1000),
    @retrievalTraceJson nvarchar(max),
    @modelName nvarchar(120)
AS
BEGIN
    SET NOCOUNT ON;

    INSERT INTO rag.AnswerAudit
    (
        ReturnCaseId,
        UserQuestion,
        Recommendation,
        Confidence,
        AnswerJson,
        CitedDocuments,
        RetrievalTraceJson,
        ModelName
    )
    VALUES
    (
        @returnCaseId,
        @userQuestion,
        @recommendation,
        @confidence,
        @answerJson,
        @citedDocuments,
        @retrievalTraceJson,
        @modelName
    );

    SELECT CAST(SCOPE_IDENTITY() AS bigint) AS AnswerAuditId;
END;
GO

CREATE OR ALTER PROCEDURE rag.usp_get_last_answers
    @topN int = 10
AS
BEGIN
    SET NOCOUNT ON;

    SELECT TOP (@topN)
        AnswerAuditId,
        ReturnCaseId,
        Recommendation,
        Confidence,
        CitedDocuments,
        ModelName,
        CreatedBy,
        CreatedAt
    FROM rag.AnswerAudit
    ORDER BY CreatedAt DESC;
END;
GO
