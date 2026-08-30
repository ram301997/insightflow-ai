import os
import re
import sqlite3
import struct
from decimal import Decimal
from typing import Any

import pyodbc
import sqlglot
from sqlglot import expressions as exp

from insightflow.config import azure_credential, require
from insightflow.demo_db import setup_demo_database


SQL_COPT_SS_ACCESS_TOKEN = 1256
SQL_TOKEN_SCOPE = "https://database.windows.net/.default"
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
MAX_ROWS = 500
QUERY_TIMEOUT_SECONDS = 30


def _base_connection_string() -> str:
    require("AZURE_SQL_SERVER", "AZURE_SQL_DATABASE")
    return (
        "Driver={ODBC Driver 18 for SQL Server};"
        f"Server=tcp:{os.environ['AZURE_SQL_SERVER']},1433;"
        f"Database={os.environ['AZURE_SQL_DATABASE']};"
        "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=15;LongAsMax=Yes;"
    )


def _token_struct() -> bytes:
    with azure_credential() as credential:
        token_bytes = credential.get_token(SQL_TOKEN_SCOPE).token.encode("utf-16-le")
    return struct.pack("<I", len(token_bytes)) + token_bytes


def connect():
    """Connect using SQL credentials when supplied, otherwise non-interactive Entra ID."""
    if os.getenv("INSIGHTFLOW_DATABASE_BACKEND", "azure_sql") == "sqlite":
        path = setup_demo_database()
        connection = sqlite3.connect(path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection
    connection_string = _base_connection_string()
    username = os.getenv("AZURE_SQL_USERNAME")
    password = os.getenv("AZURE_SQL_PASSWORD")
    if username and password:
        return pyodbc.connect(
            connection_string,
            uid=username,
            pwd=password,
        )
    return pyodbc.connect(
        connection_string,
        attrs_before={SQL_COPT_SS_ACCESS_TOKEN: _token_struct()},
    )


def using_sqlite() -> bool:
    return os.getenv("INSIGHTFLOW_DATABASE_BACKEND", "azure_sql") == "sqlite"


def _json_value(value: Any):
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def rows_as_dicts(cursor, limit: int = MAX_ROWS):
    columns = [column[0] for column in cursor.description]
    rows = cursor.fetchmany(limit + 1)
    truncated = len(rows) > limit
    data = [
        {name: _json_value(value) for name, value in zip(columns, row)}
        for row in rows[:limit]
    ]
    return data, truncated


def validate_identifier(value: str, label: str) -> str:
    if not IDENTIFIER.fullmatch(value):
        raise ValueError(f"Invalid {label}: {value!r}")
    return value


def _blocked_columns() -> set[tuple[str | None, str]]:
    """Parse SENSITIVE_COLUMNS into (table_or_None, column) pairs, lowercased.

    Entries are comma-separated. "ColumnName" blocks that column on every table; "Table.ColumnName"
    blocks it only on that table (validate_readonly_sql resolves aliases before checking, so a
    renamed table still gets caught).
    """
    raw = os.getenv("SENSITIVE_COLUMNS", "")
    blocked: set[tuple[str | None, str]] = set()
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        if "." in entry:
            table, column = entry.rsplit(".", 1)
            blocked.add((table.strip().lower(), column.strip().lower()))
        else:
            blocked.add((None, entry.lower()))
    return blocked


def is_column_blocked(column: str, table: str | None = None) -> bool:
    blocked = _blocked_columns()
    if not blocked:
        return False
    column_l = column.lower()
    if (None, column_l) in blocked:
        return True
    return bool(table) and (table.lower(), column_l) in blocked


def validate_readonly_sql(query: str) -> str:
    """Accept exactly one T-SQL query and reject every mutating construct."""
    if len(query) > 20_000:
        raise ValueError("Query is too long")
    normalized = re.sub(r"\s+", " ", query).lower()
    blocked_tokens = (
        "openrowset",
        "opendatasource",
        "openquery",
        "bulk insert",
        "xp_",
        "sp_configure",
        "execute ",
        "exec ",
    )
    if any(token in normalized for token in blocked_tokens):
        raise ValueError("External access and executable procedures are not allowed")
    statements = sqlglot.parse(query, read="tsql")
    if len(statements) != 1 or not isinstance(statements[0], exp.Query):
        raise ValueError("Only one SELECT or WITH query is allowed")

    statement = statements[0]
    forbidden = (
        exp.Insert,
        exp.Update,
        exp.Delete,
        exp.Create,
        exp.Drop,
        exp.Alter,
        exp.Merge,
        exp.Command,
        exp.Into,
        exp.Transaction,
    )
    if any(statement.find(node_type) is not None for node_type in forbidden):
        raise ValueError("Only read-only SQL is allowed")

    for table in statement.find_all(exp.Table):
        if table.catalog:
            raise ValueError("Cross-database queries are not allowed")
        schema = table.db
        if schema and schema.lower() in {"sys", "information_schema"}:
            raise ValueError("System catalogs must be accessed through metadata tools")

    if _blocked_columns():
        if statement.find(exp.Star) is not None:
            raise ValueError(
                "SELECT * is not allowed while restricted columns are configured — "
                "list explicit columns instead"
            )
        # sqlglot does no schema resolution, so a column's real table isn't always known: resolve
        # aliases to real table names, and for an unqualified column (or one qualified by something
        # we can't resolve), check it against every table in the query rather than assuming it's
        # not the restricted one — the safe direction for a security guard is to over-block.
        alias_to_table: dict[str, str] = {}
        table_names: set[str] = set()
        for table in statement.find_all(exp.Table):
            if not table.name:
                continue
            real_name = table.name.lower()
            table_names.add(real_name)
            alias_to_table[(table.alias or table.name).lower()] = real_name

        for column in statement.find_all(exp.Column):
            if column.table:
                candidates = [alias_to_table.get(column.table.lower(), column.table.lower())]
            else:
                candidates = list(table_names) or [None]
            if any(is_column_blocked(column.name, candidate) for candidate in candidates):
                raise ValueError(f"Column '{column.name}' is restricted and cannot be queried")

    return query.strip().rstrip(";")
