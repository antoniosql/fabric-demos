PRINT '00_create_schemas.sql';
GO

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = N'fraso')
BEGIN
    EXEC(N'CREATE SCHEMA fraso AUTHORIZATION dbo;');
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = N'rag')
BEGIN
    EXEC(N'CREATE SCHEMA rag AUTHORIZATION dbo;');
END;
GO
