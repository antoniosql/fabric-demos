PRINT '90_optional_vector_preview.sql';
GO

/*
    Optional preview path.

    Ejecuta este script solo si tu SQL Database in Fabric tiene habilitado el tipo vector.
    El camino principal de la demo no depende de este script.
*/

BEGIN TRY
    IF COL_LENGTH(N'rag.Chunks', N'EmbeddingVector') IS NULL
    BEGIN
        EXEC(N'ALTER TABLE rag.Chunks ADD EmbeddingVector vector(64) NULL;');
        PRINT 'Column rag.Chunks.EmbeddingVector created.';
    END
END TRY
BEGIN CATCH
    PRINT 'Vector type not available or not enabled in this database. Skipping optional vector column.';
    PRINT ERROR_MESSAGE();
END CATCH;
GO

BEGIN TRY
    EXEC(N'
CREATE OR ALTER PROCEDURE rag.usp_vector_preview_status
AS
BEGIN
    SET NOCOUNT ON;
    SELECT
        message = ''Vector preview object created. Populate rag.Chunks.EmbeddingVector and use VECTOR_DISTANCE for semantic search.'',
        chunk_count = COUNT_BIG(*)
    FROM rag.Chunks;
END;');
END TRY
BEGIN CATCH
    PRINT 'Could not create optional vector procedure.';
    PRINT ERROR_MESSAGE();
END CATCH;
GO
