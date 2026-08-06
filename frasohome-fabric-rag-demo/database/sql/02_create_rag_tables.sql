PRINT '02_create_rag_tables.sql';
GO

IF OBJECT_ID(N'rag.Documents', N'U') IS NULL
BEGIN
    CREATE TABLE rag.Documents
    (
        DocumentId       int IDENTITY(1,1) NOT NULL CONSTRAINT PK_RagDocuments PRIMARY KEY,
        DocumentCode     varchar(50)       NOT NULL,
        DocumentTitle    nvarchar(200)     NOT NULL,
        DocumentType     varchar(50)       NOT NULL,
        ValidFrom        date              NOT NULL,
        ValidTo          date              NULL,
        SecurityLevel    varchar(30)       NOT NULL,
        SourceUri        nvarchar(500)     NULL,
        Content          nvarchar(max)     NOT NULL,
        CreatedAt        datetime2(3)      NOT NULL CONSTRAINT DF_RagDocuments_CreatedAt DEFAULT SYSUTCDATETIME(),
        CONSTRAINT UQ_RagDocuments_DocumentCode UNIQUE(DocumentCode)
    );
END;
GO

IF OBJECT_ID(N'rag.Chunks', N'U') IS NULL
BEGIN
    CREATE TABLE rag.Chunks
    (
        ChunkId          bigint IDENTITY(1,1) NOT NULL CONSTRAINT PK_RagChunks PRIMARY KEY,
        DocumentId       int                  NOT NULL,
        ChunkNumber      int                  NOT NULL,
        ChunkText        nvarchar(max)        NOT NULL,
        ProductCategory  varchar(80)          NULL,
        Channel          varchar(40)          NULL,
        CountryCode      varchar(10)          NULL,
        ValidFrom        date                 NOT NULL,
        ValidTo          date                 NULL,
        Keywords         nvarchar(400)        NULL,
        CreatedAt        datetime2(3)         NOT NULL CONSTRAINT DF_RagChunks_CreatedAt DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_RagChunks_Documents FOREIGN KEY (DocumentId) REFERENCES rag.Documents(DocumentId),
        CONSTRAINT UQ_RagChunks_Document_Chunk UNIQUE(DocumentId, ChunkNumber)
    );
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_RagChunks_Filter' AND object_id = OBJECT_ID(N'rag.Chunks'))
BEGIN
    CREATE INDEX IX_RagChunks_Filter ON rag.Chunks(CountryCode, Channel, ProductCategory, ValidFrom, ValidTo);
END;
GO

IF OBJECT_ID(N'rag.ChunkEmbeddings', N'U') IS NULL
BEGIN
    CREATE TABLE rag.ChunkEmbeddings
    (
        ChunkId              bigint          NOT NULL CONSTRAINT PK_RagChunkEmbeddings PRIMARY KEY,
        EmbeddingModel       nvarchar(120)   NOT NULL,
        EmbeddingDimensions  int             NOT NULL,
        EmbeddingJson        nvarchar(max)   NOT NULL,
        UpdatedAt            datetime2(3)    NOT NULL CONSTRAINT DF_RagChunkEmbeddings_UpdatedAt DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_RagChunkEmbeddings_Chunks FOREIGN KEY (ChunkId) REFERENCES rag.Chunks(ChunkId)
    );
END;
GO

IF OBJECT_ID(N'rag.AnswerAudit', N'U') IS NULL
BEGIN
    CREATE TABLE rag.AnswerAudit
    (
        AnswerAuditId       bigint IDENTITY(1,1) NOT NULL CONSTRAINT PK_RagAnswerAudit PRIMARY KEY,
        ReturnCaseId        varchar(30)          NOT NULL,
        UserQuestion        nvarchar(max)        NOT NULL,
        Recommendation      nvarchar(200)        NOT NULL,
        Confidence          decimal(5,4)         NOT NULL,
        AnswerJson          nvarchar(max)        NOT NULL,
        CitedDocuments      nvarchar(1000)       NULL,
        RetrievalTraceJson  nvarchar(max)        NULL,
        ModelName           nvarchar(120)        NULL,
        CreatedBy           sysname              NOT NULL CONSTRAINT DF_RagAnswerAudit_CreatedBy DEFAULT SUSER_SNAME(),
        CreatedAt           datetime2(3)         NOT NULL CONSTRAINT DF_RagAnswerAudit_CreatedAt DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_RagAnswerAudit_ReturnCases FOREIGN KEY (ReturnCaseId) REFERENCES fraso.ReturnCases(ReturnCaseId)
    );
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_RagAnswerAudit_ReturnCase_CreatedAt' AND object_id = OBJECT_ID(N'rag.AnswerAudit'))
BEGIN
    CREATE INDEX IX_RagAnswerAudit_ReturnCase_CreatedAt ON rag.AnswerAudit(ReturnCaseId, CreatedAt DESC);
END;
GO
