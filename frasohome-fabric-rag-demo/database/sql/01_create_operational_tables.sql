PRINT '01_create_operational_tables.sql';
GO

IF OBJECT_ID(N'fraso.Customers', N'U') IS NULL
BEGIN
    CREATE TABLE fraso.Customers
    (
        CustomerId        varchar(20)      NOT NULL CONSTRAINT PK_Customers PRIMARY KEY,
        CustomerName      nvarchar(200)    NOT NULL,
        Segment           varchar(30)      NOT NULL,
        ReturnRiskScore   decimal(5,4)     NOT NULL,
        City              nvarchar(100)    NULL,
        Email             nvarchar(320)    NULL,
        CreatedAt         datetime2(3)     NOT NULL CONSTRAINT DF_Customers_CreatedAt DEFAULT SYSUTCDATETIME()
    );
END;
GO

IF OBJECT_ID(N'fraso.Products', N'U') IS NULL
BEGIN
    CREATE TABLE fraso.Products
    (
        ProductId       varchar(30)      NOT NULL CONSTRAINT PK_Products PRIMARY KEY,
        ProductName     nvarchar(200)    NOT NULL,
        Category        varchar(80)      NOT NULL,
        Subcategory     varchar(80)      NULL,
        IsBulky         bit              NOT NULL,
        IsCustomMade    bit              NOT NULL,
        WarrantyMonths  int              NOT NULL,
        ListPrice       decimal(12,2)    NOT NULL,
        CreatedAt       datetime2(3)     NOT NULL CONSTRAINT DF_Products_CreatedAt DEFAULT SYSUTCDATETIME()
    );
END;
GO

IF OBJECT_ID(N'fraso.Orders', N'U') IS NULL
BEGIN
    CREATE TABLE fraso.Orders
    (
        OrderId        varchar(30)      NOT NULL CONSTRAINT PK_Orders PRIMARY KEY,
        CustomerId     varchar(20)      NOT NULL,
        OrderDate      date             NOT NULL,
        DeliveryDate   date             NULL,
        Channel        varchar(40)      NOT NULL,
        StoreId        varchar(30)      NULL,
        Status         varchar(40)      NOT NULL,
        TotalAmount    decimal(12,2)    NOT NULL,
        CreatedAt      datetime2(3)     NOT NULL CONSTRAINT DF_Orders_CreatedAt DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_Orders_Customers FOREIGN KEY (CustomerId) REFERENCES fraso.Customers(CustomerId)
    );
END;
GO

IF OBJECT_ID(N'fraso.OrderLines', N'U') IS NULL
BEGIN
    CREATE TABLE fraso.OrderLines
    (
        OrderLineId  int IDENTITY(1,1) NOT NULL CONSTRAINT PK_OrderLines PRIMARY KEY,
        OrderId      varchar(30)       NOT NULL,
        ProductId    varchar(30)       NOT NULL,
        Quantity     int               NOT NULL,
        UnitPrice    decimal(12,2)     NOT NULL,
        CONSTRAINT FK_OrderLines_Orders FOREIGN KEY (OrderId) REFERENCES fraso.Orders(OrderId),
        CONSTRAINT FK_OrderLines_Products FOREIGN KEY (ProductId) REFERENCES fraso.Products(ProductId)
    );
END;
GO

IF OBJECT_ID(N'fraso.Stock', N'U') IS NULL
BEGIN
    CREATE TABLE fraso.Stock
    (
        ProductId       varchar(30)      NOT NULL,
        LocationCode    varchar(30)      NOT NULL,
        LocationName    nvarchar(120)    NOT NULL,
        AvailableUnits  int              NOT NULL,
        SafetyStock     int              NOT NULL CONSTRAINT DF_Stock_SafetyStock DEFAULT 1,
        UpdatedAt       datetime2(3)     NOT NULL CONSTRAINT DF_Stock_UpdatedAt DEFAULT SYSUTCDATETIME(),
        CONSTRAINT PK_Stock PRIMARY KEY (ProductId, LocationCode),
        CONSTRAINT FK_Stock_Products FOREIGN KEY (ProductId) REFERENCES fraso.Products(ProductId)
    );
END;
GO

IF OBJECT_ID(N'fraso.ReturnCases', N'U') IS NULL
BEGIN
    CREATE TABLE fraso.ReturnCases
    (
        ReturnCaseId      varchar(30)      NOT NULL CONSTRAINT PK_ReturnCases PRIMARY KEY,
        CustomerId        varchar(20)      NOT NULL,
        OrderId           varchar(30)      NOT NULL,
        ProductId         varchar(30)      NOT NULL,
        OpenedAt          datetime2(3)     NOT NULL,
        ReasonText        nvarchar(max)    NOT NULL,
        HasPhotos         bit              NOT NULL,
        DesiredOutcome    varchar(40)      NOT NULL,
        Status            varchar(40)      NOT NULL,
        CreatedAt         datetime2(3)     NOT NULL CONSTRAINT DF_ReturnCases_CreatedAt DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_ReturnCases_Customers FOREIGN KEY (CustomerId) REFERENCES fraso.Customers(CustomerId),
        CONSTRAINT FK_ReturnCases_Orders FOREIGN KEY (OrderId) REFERENCES fraso.Orders(OrderId),
        CONSTRAINT FK_ReturnCases_Products FOREIGN KEY (ProductId) REFERENCES fraso.Products(ProductId)
    );
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_ReturnCases_Customer_Order' AND object_id = OBJECT_ID(N'fraso.ReturnCases'))
BEGIN
    CREATE INDEX IX_ReturnCases_Customer_Order ON fraso.ReturnCases(CustomerId, OrderId);
END;
GO
