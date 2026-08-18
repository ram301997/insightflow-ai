IF OBJECT_ID('dbo.DimProduct','U') IS NULL
BEGIN
    CREATE TABLE dbo.DimProduct (
        ProductId INT PRIMARY KEY,
        ProductName NVARCHAR(200) NOT NULL,
        Category NVARCHAR(100) NOT NULL,
        UnitCost DECIMAL(18,2) NOT NULL
    );
END;
GO

IF OBJECT_ID('dbo.DimStore','U') IS NULL
BEGIN
    CREATE TABLE dbo.DimStore (
        StoreId INT PRIMARY KEY,
        StoreName NVARCHAR(200) NOT NULL,
        City NVARCHAR(100) NOT NULL,
        State NVARCHAR(100) NOT NULL
    );
END;
GO

IF OBJECT_ID('dbo.DimCustomer','U') IS NULL
BEGIN
    CREATE TABLE dbo.DimCustomer (
        CustomerId INT PRIMARY KEY,
        CustomerName NVARCHAR(200) NOT NULL,
        Segment NVARCHAR(100) NOT NULL
    );
END;
GO

IF OBJECT_ID('dbo.DimDate','U') IS NULL
BEGIN
    CREATE TABLE dbo.DimDate (
        DateId INT PRIMARY KEY,
        FullDate DATE NOT NULL UNIQUE,
        MonthNumber INT NOT NULL,
        MonthName NVARCHAR(20) NOT NULL,
        QuarterNumber INT NOT NULL,
        YearNumber INT NOT NULL
    );
END;
GO

IF OBJECT_ID('dbo.FactSales','U') IS NULL
BEGIN
    CREATE TABLE dbo.FactSales (
        SaleId INT PRIMARY KEY,
        ProductId INT NOT NULL,
        StoreId INT NOT NULL,
        CustomerId INT NOT NULL,
        DateId INT NOT NULL,
        Channel NVARCHAR(50) NOT NULL,
        Quantity INT NOT NULL,
        Revenue DECIMAL(18,2) NOT NULL,
        Cost DECIMAL(18,2) NOT NULL,
        Profit DECIMAL(18,2) NOT NULL,
        CONSTRAINT FK_FactSales_Product FOREIGN KEY (ProductId) REFERENCES dbo.DimProduct(ProductId),
        CONSTRAINT FK_FactSales_Store FOREIGN KEY (StoreId) REFERENCES dbo.DimStore(StoreId),
        CONSTRAINT FK_FactSales_Customer FOREIGN KEY (CustomerId) REFERENCES dbo.DimCustomer(CustomerId),
        CONSTRAINT FK_FactSales_Date FOREIGN KEY (DateId) REFERENCES dbo.DimDate(DateId)
    );
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_FactSales_ProductId' AND object_id = OBJECT_ID('dbo.FactSales'))
    CREATE INDEX IX_FactSales_ProductId ON dbo.FactSales(ProductId);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_FactSales_StoreId' AND object_id = OBJECT_ID('dbo.FactSales'))
    CREATE INDEX IX_FactSales_StoreId ON dbo.FactSales(StoreId);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_FactSales_DateId' AND object_id = OBJECT_ID('dbo.FactSales'))
    CREATE INDEX IX_FactSales_DateId ON dbo.FactSales(DateId);
GO
