import os
import pyodbc


def _connection_string() -> str:
    server = os.environ["AZURE_SQL_SERVER"]
    database = os.environ["AZURE_SQL_DATABASE"]

    # Explicit auth mode avoids false environment detection in browser/Cloud Shell VS Code.
    # Local development should set ActiveDirectoryDefault.
    # Azure Function App can omit this setting and defaults to managed identity.
    authentication = os.getenv("AZURE_SQL_AUTHENTICATION", "ActiveDirectoryMsi")

    return (
        "Driver={ODBC Driver 18 for SQL Server};"
        f"Server=tcp:{server},1433;"
        f"Database={database};"
        f"Authentication={authentication};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
        "Connection Timeout=30;"
    )


def connect():
    return pyodbc.connect(_connection_string())


def rows_as_dicts(cursor):
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def get_top_products(state: str, days: int = 90, top: int = 5):
    days = max(1, min(int(days), 730))
    top = max(1, min(int(top), 25))

    # The table/column structure is fixed in application code. User values are parameters.
    sql = f"""
        SELECT TOP {top}
            p.ProductName,
            SUM(fs.Revenue) AS TotalRevenue,
            SUM(fs.Profit) AS TotalProfit,
            SUM(fs.Quantity) AS UnitsSold
        FROM dbo.FactSales fs
        INNER JOIN dbo.DimProduct p ON fs.ProductId = p.ProductId
        INNER JOIN dbo.DimStore s ON fs.StoreId = s.StoreId
        INNER JOIN dbo.DimDate d ON fs.DateId = d.DateId
        WHERE s.State = ?
          AND d.FullDate >= DATEADD(DAY, -?, CAST(GETDATE() AS DATE))
        GROUP BY p.ProductName
        ORDER BY TotalRevenue DESC;
    """

    with connect() as connection:
        cursor = connection.cursor()
        cursor.execute(sql, state, days)
        return rows_as_dicts(cursor)


def get_kpis(state: str | None = None, days: int = 90):
    days = max(1, min(int(days), 730))
    where_state = " AND s.State = ?" if state else ""
    sql = f"""
        SELECT
            SUM(fs.Revenue) AS TotalRevenue,
            SUM(fs.Profit) AS TotalProfit,
            SUM(fs.Quantity) AS UnitsSold,
            COUNT(DISTINCT fs.SaleId) AS TotalOrders,
            COUNT(DISTINCT fs.CustomerId) AS TotalCustomers
        FROM dbo.FactSales fs
        INNER JOIN dbo.DimStore s ON fs.StoreId = s.StoreId
        INNER JOIN dbo.DimDate d ON fs.DateId = d.DateId
        WHERE d.FullDate >= DATEADD(DAY, -?, CAST(GETDATE() AS DATE))
        {where_state};
    """

    params = [days]
    if state:
        params.append(state)

    with connect() as connection:
        cursor = connection.cursor()
        cursor.execute(sql, *params)
        rows = rows_as_dicts(cursor)
        return rows[0] if rows else {}
