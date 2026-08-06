PRINT '03_seed_operational_data.sql';
GO

MERGE fraso.Customers AS target
USING (VALUES
    ('C-10987', N'Laura Méndez', 'Gold', CAST(0.1200 AS decimal(5,4)), N'Madrid', N'laura.mendez@example.com'),
    ('C-22041', N'Marcos Rivas', 'Standard', CAST(0.4100 AS decimal(5,4)), N'Valencia', N'marcos.rivas@example.com'),
    ('C-77731', N'Ana Torres', 'Platinum', CAST(0.0800 AS decimal(5,4)), N'Barcelona', N'ana.torres@example.com')
) AS source(CustomerId, CustomerName, Segment, ReturnRiskScore, City, Email)
ON target.CustomerId = source.CustomerId
WHEN MATCHED THEN UPDATE SET
    CustomerName = source.CustomerName,
    Segment = source.Segment,
    ReturnRiskScore = source.ReturnRiskScore,
    City = source.City,
    Email = source.Email
WHEN NOT MATCHED THEN INSERT(CustomerId, CustomerName, Segment, ReturnRiskScore, City, Email)
VALUES(source.CustomerId, source.CustomerName, source.Segment, source.ReturnRiskScore, source.City, source.Email);
GO

MERGE fraso.Products AS target
USING (VALUES
    ('P-SOFA-NORDIC-3', N'Sofá modular Nordic 3 plazas', 'furniture', 'sofas', CAST(1 AS bit), CAST(0 AS bit), 36, CAST(1299.00 AS decimal(12,2))),
    ('P-LAMP-OSLO', N'Lámpara Oslo de pie', 'lighting', 'lamps', CAST(0 AS bit), CAST(0 AS bit), 24, CAST(149.00 AS decimal(12,2))),
    ('P-TABLE-CUSTOM-OAK', N'Mesa de roble a medida', 'furniture', 'tables', CAST(1 AS bit), CAST(1 AS bit), 36, CAST(899.00 AS decimal(12,2)))
) AS source(ProductId, ProductName, Category, Subcategory, IsBulky, IsCustomMade, WarrantyMonths, ListPrice)
ON target.ProductId = source.ProductId
WHEN MATCHED THEN UPDATE SET
    ProductName = source.ProductName,
    Category = source.Category,
    Subcategory = source.Subcategory,
    IsBulky = source.IsBulky,
    IsCustomMade = source.IsCustomMade,
    WarrantyMonths = source.WarrantyMonths,
    ListPrice = source.ListPrice
WHEN NOT MATCHED THEN INSERT(ProductId, ProductName, Category, Subcategory, IsBulky, IsCustomMade, WarrantyMonths, ListPrice)
VALUES(source.ProductId, source.ProductName, source.Category, source.Subcategory, source.IsBulky, source.IsCustomMade, source.WarrantyMonths, source.ListPrice);
GO

MERGE fraso.Orders AS target
USING (VALUES
    ('WEB-883192', 'C-10987', CONVERT(date,'2026-05-05'), CONVERT(date,'2026-05-11'), 'ecommerce', NULL, 'delivered', CAST(1299.00 AS decimal(12,2))),
    ('WEB-883190', 'C-22041', CONVERT(date,'2026-05-20'), CONVERT(date,'2026-05-23'), 'ecommerce', NULL, 'delivered', CAST(149.00 AS decimal(12,2))),
    ('POS-100772', 'C-77731', CONVERT(date,'2026-06-01'), CONVERT(date,'2026-06-01'), 'store', 'MAD-CENTRO', 'delivered', CAST(899.00 AS decimal(12,2)))
) AS source(OrderId, CustomerId, OrderDate, DeliveryDate, Channel, StoreId, Status, TotalAmount)
ON target.OrderId = source.OrderId
WHEN MATCHED THEN UPDATE SET
    CustomerId = source.CustomerId,
    OrderDate = source.OrderDate,
    DeliveryDate = source.DeliveryDate,
    Channel = source.Channel,
    StoreId = source.StoreId,
    Status = source.Status,
    TotalAmount = source.TotalAmount
WHEN NOT MATCHED THEN INSERT(OrderId, CustomerId, OrderDate, DeliveryDate, Channel, StoreId, Status, TotalAmount)
VALUES(source.OrderId, source.CustomerId, source.OrderDate, source.DeliveryDate, source.Channel, source.StoreId, source.Status, source.TotalAmount);
GO

IF NOT EXISTS (SELECT 1 FROM fraso.OrderLines WHERE OrderId = 'WEB-883192' AND ProductId = 'P-SOFA-NORDIC-3')
BEGIN
    INSERT INTO fraso.OrderLines(OrderId, ProductId, Quantity, UnitPrice)
    VALUES('WEB-883192', 'P-SOFA-NORDIC-3', 1, 1299.00);
END;
GO

IF NOT EXISTS (SELECT 1 FROM fraso.OrderLines WHERE OrderId = 'WEB-883190' AND ProductId = 'P-LAMP-OSLO')
BEGIN
    INSERT INTO fraso.OrderLines(OrderId, ProductId, Quantity, UnitPrice)
    VALUES('WEB-883190', 'P-LAMP-OSLO', 1, 149.00);
END;
GO

IF NOT EXISTS (SELECT 1 FROM fraso.OrderLines WHERE OrderId = 'POS-100772' AND ProductId = 'P-TABLE-CUSTOM-OAK')
BEGIN
    INSERT INTO fraso.OrderLines(OrderId, ProductId, Quantity, UnitPrice)
    VALUES('POS-100772', 'P-TABLE-CUSTOM-OAK', 1, 899.00);
END;
GO

MERGE fraso.Stock AS target
USING (VALUES
    ('P-SOFA-NORDIC-3', 'MAD-SUR', N'Almacén Madrid Sur', 8, 2),
    ('P-SOFA-NORDIC-3', 'BCN-ZAL', N'Almacén Barcelona ZAL', 3, 1),
    ('P-LAMP-OSLO', 'MAD-SUR', N'Almacén Madrid Sur', 27, 4),
    ('P-TABLE-CUSTOM-OAK', 'MAD-SUR', N'Almacén Madrid Sur', 0, 0)
) AS source(ProductId, LocationCode, LocationName, AvailableUnits, SafetyStock)
ON target.ProductId = source.ProductId AND target.LocationCode = source.LocationCode
WHEN MATCHED THEN UPDATE SET
    LocationName = source.LocationName,
    AvailableUnits = source.AvailableUnits,
    SafetyStock = source.SafetyStock,
    UpdatedAt = SYSUTCDATETIME()
WHEN NOT MATCHED THEN INSERT(ProductId, LocationCode, LocationName, AvailableUnits, SafetyStock)
VALUES(source.ProductId, source.LocationCode, source.LocationName, source.AvailableUnits, source.SafetyStock);
GO

MERGE fraso.ReturnCases AS target
USING (VALUES
    ('RET-2026-004219', 'C-10987', 'WEB-883192', 'P-SOFA-NORDIC-3', CONVERT(datetime2(3),'2026-06-14T10:42:00'), N'El sofá llegó con una pata dañada y el embalaje exterior presentaba golpes visibles. El cliente adjunta fotos y pide reemplazo urgente.', CAST(1 AS bit), 'replacement', 'open'),
    ('RET-2026-004220', 'C-22041', 'WEB-883190', 'P-LAMP-OSLO', CONVERT(datetime2(3),'2026-06-15T09:10:00'), N'El cliente quiere devolver la lámpara porque no encaja con la decoración.', CAST(0 AS bit), 'refund', 'open'),
    ('RET-2026-004221', 'C-77731', 'POS-100772', 'P-TABLE-CUSTOM-OAK', CONVERT(datetime2(3),'2026-06-15T11:20:00'), N'La mesa a medida no cabe en la estancia. Solicita devolución.', CAST(0 AS bit), 'refund', 'open')
) AS source(ReturnCaseId, CustomerId, OrderId, ProductId, OpenedAt, ReasonText, HasPhotos, DesiredOutcome, Status)
ON target.ReturnCaseId = source.ReturnCaseId
WHEN MATCHED THEN UPDATE SET
    CustomerId = source.CustomerId,
    OrderId = source.OrderId,
    ProductId = source.ProductId,
    OpenedAt = source.OpenedAt,
    ReasonText = source.ReasonText,
    HasPhotos = source.HasPhotos,
    DesiredOutcome = source.DesiredOutcome,
    Status = source.Status
WHEN NOT MATCHED THEN INSERT(ReturnCaseId, CustomerId, OrderId, ProductId, OpenedAt, ReasonText, HasPhotos, DesiredOutcome, Status)
VALUES(source.ReturnCaseId, source.CustomerId, source.OrderId, source.ProductId, source.OpenedAt, source.ReasonText, source.HasPhotos, source.DesiredOutcome, source.Status);
GO
