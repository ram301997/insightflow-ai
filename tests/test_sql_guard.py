import unittest
from unittest.mock import patch

from insightflow.sql import is_column_blocked, validate_identifier, validate_readonly_sql


class SqlGuardTests(unittest.TestCase):
    def setUp(self):
        # Tests must not depend on whatever SENSITIVE_COLUMNS happens to be set in the real .env —
        # start each test from "no restrictions configured" unless it opts in via patch.dict.
        patcher = patch.dict("os.environ", {"SENSITIVE_COLUMNS": ""})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_select_is_allowed(self):
        query = "SELECT TOP 5 ProductId, SUM(Revenue) AS Revenue FROM dbo.FactSales GROUP BY ProductId"
        self.assertEqual(validate_readonly_sql(query), query)

    def test_cte_is_allowed(self):
        query = "WITH totals AS (SELECT ProductId, SUM(Revenue) AS Revenue FROM dbo.FactSales GROUP BY ProductId) SELECT * FROM totals"
        self.assertEqual(validate_readonly_sql(query), query)

    def test_multiple_statements_are_rejected(self):
        with self.assertRaises(ValueError):
            validate_readonly_sql("SELECT 1; SELECT 2")

    def test_mutation_is_rejected(self):
        for query in (
            "DELETE FROM dbo.FactSales",
            "UPDATE dbo.FactSales SET Revenue = 0",
            "SELECT * INTO dbo.CopyOfSales FROM dbo.FactSales",
        ):
            with self.subTest(query=query), self.assertRaises(ValueError):
                validate_readonly_sql(query)

    def test_cross_database_query_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_readonly_sql("SELECT * FROM OtherDatabase.dbo.FactSales")

    def test_external_access_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_readonly_sql("SELECT * FROM OPENROWSET(BULK 'file.csv', FORMAT='CSV') AS rows")

    def test_identifier_validation(self):
        self.assertEqual(validate_identifier("FactSales", "table"), "FactSales")
        with self.assertRaises(ValueError):
            validate_identifier("FactSales]; DROP TABLE x--", "table")

    @patch.dict("os.environ", {"SENSITIVE_COLUMNS": "SSN,DimCustomer.Email"})
    def test_bare_sensitive_column_is_blocked_on_any_table(self):
        self.assertTrue(is_column_blocked("SSN", "DimCustomer"))
        self.assertTrue(is_column_blocked("ssn", "AnyOtherTable"))
        with self.assertRaises(ValueError):
            validate_readonly_sql("SELECT SSN FROM dbo.DimCustomer")

    @patch.dict("os.environ", {"SENSITIVE_COLUMNS": "SSN,DimCustomer.Email"})
    def test_table_qualified_sensitive_column_is_scoped(self):
        self.assertTrue(is_column_blocked("Email", "DimCustomer"))
        self.assertFalse(is_column_blocked("Email", "DimStore"))
        with self.assertRaises(ValueError):
            validate_readonly_sql("SELECT DimCustomer.Email FROM dbo.DimCustomer")

    @patch.dict("os.environ", {"SENSITIVE_COLUMNS": "DimCustomer.Email"})
    def test_table_qualified_form_catches_unqualified_columns_too(self):
        """An unqualified column is checked against every table in the query, not just the alias-resolved one."""
        with self.assertRaises(ValueError):
            validate_readonly_sql("SELECT Email FROM dbo.DimCustomer")

    @patch.dict("os.environ", {"SENSITIVE_COLUMNS": "DimCustomer.Email"})
    def test_table_qualified_form_survives_an_alias(self):
        with self.assertRaises(ValueError):
            validate_readonly_sql("SELECT c.Email FROM dbo.DimCustomer AS c")

    @patch.dict("os.environ", {"SENSITIVE_COLUMNS": "SSN"})
    def test_select_star_is_rejected_when_columns_are_restricted(self):
        with self.assertRaises(ValueError):
            validate_readonly_sql("SELECT * FROM dbo.DimCustomer")

    @patch.dict("os.environ", {"SENSITIVE_COLUMNS": "SSN"})
    def test_unrelated_columns_still_allowed_when_restrictions_configured(self):
        query = "SELECT ProductId, SUM(Revenue) AS Revenue FROM dbo.FactSales GROUP BY ProductId"
        self.assertEqual(validate_readonly_sql(query), query)

    def test_no_restrictions_configured_means_nothing_blocked(self):
        self.assertFalse(is_column_blocked("SSN", "DimCustomer"))


if __name__ == "__main__":
    unittest.main()
