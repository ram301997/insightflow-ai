IF NOT EXISTS (SELECT 1 FROM dbo.DimProduct)
BEGIN
    INSERT INTO dbo.DimProduct (ProductId, ProductName, Category, UnitCost) VALUES
    (1,'Laptop Pro','Computers',900.00),(2,'Laptop Air','Computers',700.00),(3,'Smartphone Pro','Phones',500.00),
    (4,'Smartphone Lite','Phones',300.00),(5,'Tablet Pro','Tablets',400.00),(6,'Tablet Mini','Tablets',250.00),
    (7,'Smart Watch','Wearables',150.00),(8,'Wireless Buds','Audio',80.00),(9,'4K Monitor','Accessories',220.00),
    (10,'Gaming Keyboard','Accessories',65.00);
END;
GO

IF NOT EXISTS (SELECT 1 FROM dbo.DimStore)
BEGIN
    INSERT INTO dbo.DimStore (StoreId, StoreName, City, State) VALUES
    (1,'Miami Central','Miami','Florida'),(2,'Orlando Market','Orlando','Florida'),(3,'Dallas Hub','Dallas','Texas'),
    (4,'Austin Tech','Austin','Texas'),(5,'Manhattan Center','New York','New York'),(6,'LA West','Los Angeles','California'),
    (7,'Chicago Loop','Chicago','Illinois'),(8,'Atlanta Midtown','Atlanta','Georgia');
END;
GO

IF NOT EXISTS (SELECT 1 FROM dbo.DimCustomer)
BEGIN
    INSERT INTO dbo.DimCustomer (CustomerId, CustomerName, Segment, Email) VALUES
    (1,'Acme Corp','Enterprise','contact01@example.com'),(2,'Northstar LLC','Small Business','contact02@example.com'),
    (3,'Blue Ocean Inc','Enterprise','contact03@example.com'),(4,'Sunrise Studio','Small Business','contact04@example.com'),
    (5,'Customer 05','Consumer','contact05@example.com'),(6,'Customer 06','Consumer','contact06@example.com'),
    (7,'Customer 07','Consumer','contact07@example.com'),(8,'Customer 08','Consumer','contact08@example.com'),
    (9,'Customer 09','Consumer','contact09@example.com'),(10,'Customer 10','Consumer','contact10@example.com'),
    (11,'Customer 11','Consumer','contact11@example.com'),(12,'Customer 12','Consumer','contact12@example.com'),
    (13,'Customer 13','Consumer','contact13@example.com'),(14,'Customer 14','Consumer','contact14@example.com'),
    (15,'Customer 15','Consumer','contact15@example.com'),(16,'Customer 16','Consumer','contact16@example.com'),
    (17,'Customer 17','Consumer','contact17@example.com'),(18,'Customer 18','Consumer','contact18@example.com'),
    (19,'Customer 19','Consumer','contact19@example.com'),(20,'Customer 20','Consumer','contact20@example.com');
END;
GO

IF NOT EXISTS (SELECT 1 FROM dbo.DimDate)
BEGIN
    ;WITH Dates AS (
        SELECT CAST('2025-01-01' AS DATE) AS FullDate
        UNION ALL
        SELECT DATEADD(DAY,1,FullDate) FROM Dates WHERE FullDate < '2026-12-31'
    )
    INSERT INTO dbo.DimDate (DateId, FullDate, MonthNumber, MonthName, QuarterNumber, YearNumber)
    SELECT CONVERT(INT, FORMAT(FullDate,'yyyyMMdd')), FullDate, MONTH(FullDate), DATENAME(MONTH,FullDate), DATEPART(QUARTER,FullDate), YEAR(FullDate)
    FROM Dates OPTION (MAXRECURSION 0);
END;
GO

IF NOT EXISTS (SELECT 1 FROM dbo.FactSales)
BEGIN
    ;WITH N AS (
        SELECT TOP (5000) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS n
        FROM sys.all_objects a CROSS JOIN sys.all_objects b
    ), X AS (
        SELECT n,
               1 + ABS(CHECKSUM(CONCAT('p',n))) % 10 AS ProductId,
               1 + ABS(CHECKSUM(CONCAT('s',n))) % 8 AS StoreId,
               1 + ABS(CHECKSUM(CONCAT('c',n))) % 20 AS CustomerId,
               DATEADD(DAY, ABS(CHECKSUM(CONCAT('d',n))) % (DATEDIFF(DAY,'2025-01-01',CASE WHEN CAST(GETDATE() AS DATE) < '2026-12-31' THEN CAST(GETDATE() AS DATE) ELSE CAST('2026-12-31' AS DATE) END)+1), CAST('2025-01-01' AS DATE)) AS SaleDate,
               1 + ABS(CHECKSUM(CONCAT('q',n))) % 5 AS Qty
        FROM N
    )
    INSERT INTO dbo.FactSales (SaleId, ProductId, StoreId, CustomerId, DateId, Channel, Quantity, Revenue, Cost, Profit)
    SELECT x.n, x.ProductId, x.StoreId, x.CustomerId, CONVERT(INT, FORMAT(x.SaleDate,'yyyyMMdd')),
           CASE ABS(CHECKSUM(CONCAT('ch',x.n))) % 3 WHEN 0 THEN 'Online' WHEN 1 THEN 'Retail' ELSE 'Partner' END,
           x.Qty,
           CAST(p.UnitCost * x.Qty * (1.25 + (ABS(CHECKSUM(CONCAT('m',x.n))) % 41) / 100.0) AS DECIMAL(18,2)),
           CAST(p.UnitCost * x.Qty AS DECIMAL(18,2)),
           CAST((p.UnitCost * x.Qty * (1.25 + (ABS(CHECKSUM(CONCAT('m',x.n))) % 41) / 100.0)) - (p.UnitCost * x.Qty) AS DECIMAL(18,2))
    FROM X x JOIN dbo.DimProduct p ON p.ProductId=x.ProductId;
END;
GO

SELECT COUNT(*) AS FactSalesRows FROM dbo.FactSales;
