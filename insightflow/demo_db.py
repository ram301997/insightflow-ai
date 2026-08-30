import os
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from insightflow.config import ROOT


DEMO_SCHEMA_VERSION = "2"


def demo_database_path() -> Path:
    return Path(os.getenv("SQLITE_DATABASE_PATH", ROOT / "data" / "insightflow-demo.db"))


def setup_demo_database() -> Path:
    """Create a deterministic, realistic local star schema on first run."""
    path = demo_database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        probe = sqlite3.connect(path)
        try:
            version = probe.execute("SELECT Value FROM AppMetadata WHERE Key='SchemaVersion'").fetchone()
        except sqlite3.OperationalError:
            version = None
        probe.close()
        # CREATE TABLE IF NOT EXISTS below won't pick up column additions on an existing file —
        # a version bump means the table shapes changed, so rebuild the file from scratch.
        if not version or version[0] != DEMO_SCHEMA_VERSION:
            path.unlink()
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS AppMetadata (Key TEXT PRIMARY KEY, Value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS DimProduct (
            ProductId INTEGER PRIMARY KEY, ProductName TEXT NOT NULL,
            Category TEXT NOT NULL, UnitCost REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS DimStore (
            StoreId INTEGER PRIMARY KEY, StoreName TEXT NOT NULL,
            City TEXT NOT NULL, State TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS DimCustomer (
            CustomerId INTEGER PRIMARY KEY, CustomerName TEXT NOT NULL,
            Segment TEXT NOT NULL, Email TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS DimDate (
            DateId INTEGER PRIMARY KEY, FullDate TEXT NOT NULL UNIQUE,
            MonthNumber INTEGER NOT NULL, MonthName TEXT NOT NULL,
            QuarterNumber INTEGER NOT NULL, YearNumber INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS FactSales (
            SaleId INTEGER PRIMARY KEY,
            ProductId INTEGER NOT NULL REFERENCES DimProduct(ProductId),
            StoreId INTEGER NOT NULL REFERENCES DimStore(StoreId),
            CustomerId INTEGER NOT NULL REFERENCES DimCustomer(CustomerId),
            DateId INTEGER NOT NULL REFERENCES DimDate(DateId),
            Channel TEXT NOT NULL, Quantity INTEGER NOT NULL,
            Revenue REAL NOT NULL, Cost REAL NOT NULL, Profit REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS IX_FactSales_ProductId ON FactSales(ProductId);
        CREATE INDEX IF NOT EXISTS IX_FactSales_StoreId ON FactSales(StoreId);
        CREATE INDEX IF NOT EXISTS IX_FactSales_DateId ON FactSales(DateId);
        """
    )
    version = connection.execute("SELECT Value FROM AppMetadata WHERE Key='SchemaVersion'").fetchone()
    row_count = connection.execute("SELECT COUNT(*) FROM FactSales").fetchone()[0]
    if version and version[0] == DEMO_SCHEMA_VERSION and row_count == 5000:
        connection.close()
        return path

    connection.executescript(
        """
        DELETE FROM FactSales; DELETE FROM DimDate; DELETE FROM DimCustomer;
        DELETE FROM DimStore; DELETE FROM DimProduct; DELETE FROM AppMetadata;
        """
    )
    products = [
        (1, "Laptop Pro", "Computers", 900.0), (2, "Laptop Air", "Computers", 700.0),
        (3, "Smartphone Pro", "Phones", 500.0), (4, "Smartphone Lite", "Phones", 300.0),
        (5, "Tablet Pro", "Tablets", 400.0), (6, "Tablet Mini", "Tablets", 250.0),
        (7, "Smart Watch", "Wearables", 150.0), (8, "Wireless Buds", "Audio", 80.0),
        (9, "4K Monitor", "Accessories", 220.0), (10, "Gaming Keyboard", "Accessories", 65.0),
    ]
    stores = [
        (1, "Miami Central", "Miami", "Florida"), (2, "Orlando Market", "Orlando", "Florida"),
        (3, "Dallas Hub", "Dallas", "Texas"), (4, "Austin Tech", "Austin", "Texas"),
        (5, "Manhattan Center", "New York", "New York"),
        (6, "LA West", "Los Angeles", "California"),
        (7, "Chicago Loop", "Chicago", "Illinois"), (8, "Atlanta Midtown", "Atlanta", "Georgia"),
    ]
    segments = ["Enterprise", "Small Business", "Consumer"]
    customers = [
        (i, f"Customer {i:02d}", segments[(i - 1) % 3], f"customer{i:02d}@example.com")
        for i in range(1, 51)
    ]
    connection.executemany("INSERT INTO DimProduct VALUES (?,?,?,?)", products)
    connection.executemany("INSERT INTO DimStore VALUES (?,?,?,?)", stores)
    connection.executemany("INSERT INTO DimCustomer VALUES (?,?,?,?)", customers)

    start = date.today() - timedelta(days=729)
    dates = []
    for offset in range(730):
        current = start + timedelta(days=offset)
        dates.append((
            int(current.strftime("%Y%m%d")), current.isoformat(), current.month,
            current.strftime("%B"), ((current.month - 1) // 3) + 1, current.year,
        ))
    connection.executemany("INSERT INTO DimDate VALUES (?,?,?,?,?,?)", dates)

    rng = random.Random(20260825)
    channels = ["Online", "Retail", "Partner"]
    sales = []
    for sale_id in range(1, 5001):
        product = products[rng.randrange(len(products))]
        quantity = rng.randint(1, 5)
        cost = round(product[3] * quantity, 2)
        revenue = round(cost * rng.uniform(1.25, 1.65), 2)
        sales.append((
            sale_id, product[0], stores[rng.randrange(len(stores))][0], rng.randint(1, 50),
            dates[rng.randrange(len(dates))][0], channels[rng.randrange(len(channels))],
            quantity, revenue, cost, round(revenue - cost, 2),
        ))
    connection.executemany("INSERT INTO FactSales VALUES (?,?,?,?,?,?,?,?,?,?)", sales)
    connection.execute("INSERT INTO AppMetadata VALUES ('SchemaVersion', ?)", (DEMO_SCHEMA_VERSION,))
    connection.commit()
    connection.close()
    return path
