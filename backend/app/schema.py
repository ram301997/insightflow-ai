SEMANTIC_SCHEMA = {
    "fact_table": "FactSales",
    "dimensions": {
        "product": ["ProductName", "Category"],
        "store": ["StoreName", "City", "State"],
        "customer": ["CustomerName", "Segment"],
        "date": ["FullDate", "MonthName", "QuarterNumber", "YearNumber"],
    },
    "metrics": {
        "revenue": "SUM(FactSales.Revenue)",
        "profit": "SUM(FactSales.Profit)",
        "units": "SUM(FactSales.Quantity)",
        "orders": "COUNT(DISTINCT FactSales.SaleId)",
        "customers": "COUNT(DISTINCT FactSales.CustomerId)",
    },
    "rules": [
        "Only approved metrics and dimensions can be queried.",
        "Do not generate or execute arbitrary SQL from user text.",
        "State, time-window, and top-N values are passed as parameters.",
    ],
}
