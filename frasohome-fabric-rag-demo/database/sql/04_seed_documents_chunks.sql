PRINT '04_seed_documents_chunks.sql';
GO

DECLARE @Documents TABLE
(
    DocumentCode   varchar(50)   NOT NULL,
    DocumentTitle  nvarchar(200) NOT NULL,
    DocumentType   varchar(50)   NOT NULL,
    ValidFrom      date          NOT NULL,
    ValidTo        date          NULL,
    SecurityLevel  varchar(30)   NOT NULL,
    SourceUri      nvarchar(500) NULL,
    Content        nvarchar(max) NOT NULL
);

INSERT INTO @Documents(DocumentCode, DocumentTitle, DocumentType, ValidFrom, ValidTo, SecurityLevel, SourceUri, Content)
VALUES
('POL-DEV-001', N'Política general de devoluciones por canal', 'policy', '2026-01-01', NULL, 'internal', N'https://frasohome.example/policies/POL-DEV-001',
 N'FraSoHome permite devoluciones estándar dentro del periodo definido por canal. Las devoluciones ecommerce deben validarse contra fecha de entrega, categoría de producto, estado del artículo, evidencias disponibles y excepciones activas. Si la política específica de categoría contradice la política general, prevalece la política específica.'),
('POL-DMG-002', N'Daños en transporte y evidencias necesarias', 'policy', '2026-01-01', NULL, 'internal', N'https://frasohome.example/policies/POL-DMG-002',
 N'Cuando un producto llega con daño visible en embalaje, estructura o piezas, el cliente debe aportar evidencia fotográfica. Si la reclamación se registra dentro del periodo permitido y existe stock, se prioriza reemplazo sobre reembolso. Para daño de transporte en muebles voluminosos se debe validar evidencia visual antes de cerrar la aprobación.'),
('POL-MUE-003', N'Productos voluminosos: recogida, costes y plazos', 'policy', '2026-01-01', NULL, 'internal', N'https://frasohome.example/policies/POL-MUE-003',
 N'Los productos voluminosos, como sofás, mesas grandes y armarios, requieren recogida coordinada. Si el daño es atribuible al transporte o entrega, la recogida no tiene coste para el cliente. Si hay stock disponible, se recomienda reservar reemplazo antes de programar la recogida.'),
('POL-VIP-004', N'Excepciones para clientes Gold y Platinum', 'policy', '2026-01-01', NULL, 'restricted', N'https://frasohome.example/policies/POL-VIP-004',
 N'Los clientes Gold y Platinum con bajo riesgo de devolución pueden recibir priorización de reemplazos y recogidas. La priorización no elimina controles de fraude ni la obligación de evidencias cuando hay daño reportado. Para clientes con riesgo inferior a 0.20, se permite aprobación condicionada a revisión visual.'),
('SOP-RET-005', N'Procedimiento interno para aprobar reemplazos', 'sop', '2026-01-01', NULL, 'internal', N'https://frasohome.example/sop/SOP-RET-005',
 N'El agente debe verificar pedido, canal, categoría, fecha de entrega, stock de reemplazo y evidencia. Cuando todos los criterios son favorables, crear orden de recogida, reservar unidad de reemplazo y dejar nota de auditoría con documentos citados.'),
('POL-WAR-006', N'Garantía legal y garantía comercial', 'policy', '2026-01-01', NULL, 'internal', N'https://frasohome.example/policies/POL-WAR-006',
 N'La garantía cubre defectos de fabricación y daños no atribuibles al uso indebido. Para daños reportados en la entrega, aplicar primero la política de daños en transporte y luego la garantía si procede. Los productos a medida tienen restricciones adicionales para devoluciones por preferencia.' );

MERGE rag.Documents AS target
USING @Documents AS source
ON target.DocumentCode = source.DocumentCode
WHEN MATCHED THEN UPDATE SET
    DocumentTitle = source.DocumentTitle,
    DocumentType = source.DocumentType,
    ValidFrom = source.ValidFrom,
    ValidTo = source.ValidTo,
    SecurityLevel = source.SecurityLevel,
    SourceUri = source.SourceUri,
    Content = source.Content
WHEN NOT MATCHED THEN INSERT(DocumentCode, DocumentTitle, DocumentType, ValidFrom, ValidTo, SecurityLevel, SourceUri, Content)
VALUES(source.DocumentCode, source.DocumentTitle, source.DocumentType, source.ValidFrom, source.ValidTo, source.SecurityLevel, source.SourceUri, source.Content);
GO

DECLARE @Chunks TABLE
(
    DocumentCode      varchar(50)   NOT NULL,
    ChunkNumber       int           NOT NULL,
    ChunkText         nvarchar(max) NOT NULL,
    ProductCategory   varchar(80)   NULL,
    Channel           varchar(40)   NULL,
    CountryCode       varchar(10)   NULL,
    Keywords          nvarchar(400) NULL
);

INSERT INTO @Chunks(DocumentCode, ChunkNumber, ChunkText, ProductCategory, Channel, CountryCode, Keywords)
VALUES
('POL-DEV-001', 1, N'Las devoluciones ecommerce deben evaluarse desde la fecha de entrega y no desde la fecha de pedido. El agente debe validar canal, categoría de producto, estado del artículo y evidencias adjuntas.', 'all', 'ecommerce', 'ES', N'devolución ecommerce entrega evidencia'),
('POL-DEV-001', 2, N'Si una política específica de categoría aplica a muebles voluminosos, daños de transporte o productos personalizados, dicha política prevalece sobre la política general de devoluciones.', 'all', 'all', 'ES', N'política específica muebles transporte personalizados'),
('POL-DMG-002', 1, N'Para daños visibles en transporte se requiere evidencia fotográfica del embalaje y del producto. Si el cliente aporta fotos, el agente puede iniciar aprobación condicionada mientras se completa revisión visual.', 'all', 'all', 'ES', N'daño transporte evidencia fotográfica embalaje aprobación condicionada'),
('POL-DMG-002', 2, N'Cuando hay daño de transporte, reclamación dentro del periodo permitido y stock disponible, FraSoHome prioriza reemplazo sobre reembolso inmediato.', 'all', 'ecommerce', 'ES', N'daño transporte stock reemplazo reembolso'),
('POL-MUE-003', 1, N'Los muebles voluminosos requieren recogida coordinada. Si el daño se atribuye a transporte o entrega, la recogida no tiene coste para el cliente.', 'furniture', 'all', 'ES', N'mueble voluminoso recogida transporte coste'),
('POL-MUE-003', 2, N'Antes de confirmar un reemplazo de mueble voluminoso, se debe reservar una unidad en almacén o tienda con disponibilidad superior al stock de seguridad.', 'furniture', 'all', 'ES', N'mueble voluminoso reemplazo stock seguridad'),
('POL-VIP-004', 1, N'Clientes Gold y Platinum con riesgo de devolución inferior a 0.20 pueden recibir priorización de reemplazo y recogida. Esta priorización requiere evidencias cuando se declara daño.', 'all', 'all', 'ES', N'Gold Platinum bajo riesgo priorización reemplazo evidencia'),
('SOP-RET-005', 1, N'El agente debe verificar pedido, canal, fecha de entrega, categoría, stock y evidencia. Si todos los criterios son favorables, crear orden de recogida, reservar reemplazo y registrar auditoría.', 'all', 'all', 'ES', N'procedimiento agente verificar pedido stock evidencia auditoría'),
('POL-WAR-006', 1, N'La garantía comercial puede aplicar si el daño no es atribuible al uso del cliente. Para daños detectados en entrega, aplicar primero la política de transporte.', 'all', 'all', 'ES', N'garantía daño entrega transporte');

MERGE rag.Chunks AS target
USING
(
    SELECT
        d.DocumentId,
        c.ChunkNumber,
        c.ChunkText,
        c.ProductCategory,
        c.Channel,
        c.CountryCode,
        d.ValidFrom,
        d.ValidTo,
        c.Keywords
    FROM @Chunks AS c
    JOIN rag.Documents AS d
        ON d.DocumentCode = c.DocumentCode
) AS source
ON target.DocumentId = source.DocumentId
   AND target.ChunkNumber = source.ChunkNumber
WHEN MATCHED THEN UPDATE SET
    ChunkText = source.ChunkText,
    ProductCategory = source.ProductCategory,
    Channel = source.Channel,
    CountryCode = source.CountryCode,
    ValidFrom = source.ValidFrom,
    ValidTo = source.ValidTo,
    Keywords = source.Keywords
WHEN NOT MATCHED THEN INSERT(DocumentId, ChunkNumber, ChunkText, ProductCategory, Channel, CountryCode, ValidFrom, ValidTo, Keywords)
VALUES(source.DocumentId, source.ChunkNumber, source.ChunkText, source.ProductCategory, source.Channel, source.CountryCode, source.ValidFrom, source.ValidTo, source.Keywords);
GO
