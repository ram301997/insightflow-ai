# Power BI model guidance

Use the Azure SQL tables as a star schema:

- Fact: `FactSales`
- Dimensions: `DimProduct`, `DimStore`, `DimCustomer`, `DimDate`

Recommended report pages:

- Sales Overview
- Product Analysis
- Regional Performance
- Customer Analysis

Initial DAX measures:

```DAX
Total Revenue = SUM(FactSales[Revenue])
Total Profit = SUM(FactSales[Profit])
Total Orders = DISTINCTCOUNT(FactSales[SaleId])
Total Customers = DISTINCTCOUNT(FactSales[CustomerId])
Profit Margin % = DIVIDE([Total Profit], [Total Revenue], 0)
```

The backend emits a `dashboardAction` object such as:

```json
{
  "page": "Product Analysis",
  "filters": [
    {
      "table": "DimStore",
      "column": "State",
      "operator": "In",
      "values": ["Florida"]
    }
  ],
  "relativeDate": {
    "days": 90
  }
}
```

In the Power BI embedding phase, the frontend will translate this object into Power BI JavaScript SDK page navigation and filters rather than creating a new report for every question.
