PRINT '06_create_security.sql';
GO

IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = N'frasohome_rag_executor' AND type = 'R')
BEGIN
    CREATE ROLE frasohome_rag_executor AUTHORIZATION dbo;
END;
GO

GRANT SELECT ON SCHEMA::fraso TO frasohome_rag_executor;
GRANT SELECT ON SCHEMA::rag TO frasohome_rag_executor;
GRANT EXECUTE ON SCHEMA::rag TO frasohome_rag_executor;
GO

PRINT 'Role frasohome_rag_executor created. Create an Entra user first, then add it as needed:';
PRINT 'CREATE USER [user@domain.com] FROM EXTERNAL PROVIDER;';
PRINT 'ALTER ROLE frasohome_rag_executor ADD MEMBER [user@domain.com];';
PRINT 'For Fabric service principals, create the user with SID = application/client id and TYPE = E.';
PRINT 'ALTER ROLE frasohome_rag_executor ADD MEMBER [service-principal-display-name];';
GO
