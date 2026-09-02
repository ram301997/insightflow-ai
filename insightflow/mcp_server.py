import base64
import json
from functools import wraps

from mcp.server.fastmcp import FastMCP

from insightflow.chart_sandbox import render_chart_image
from insightflow.sql import (
    MAX_ROWS,
    QUERY_TIMEOUT_SECONDS,
    connect,
    is_column_blocked,
    rows_as_dicts,
    validate_identifier,
    validate_readonly_sql,
)


mcp = FastMCP(
    "InsightFlow Azure SQL",
    instructions=(
        "Read-only business intelligence access to Azure SQL. Inspect table and relationship "
        "metadata before writing a query. Never invent columns or business metrics."
    ),
)


def _result(data, **metadata) -> str:
    return json.dumps({"data": data, **metadata}, default=str)


def _cursor(connection):
    cursor = connection.cursor()
    if hasattr(cursor, "timeout"):
        cursor.timeout = QUERY_TIMEOUT_SECONDS
    return cursor


def safe_tool(function):
    """Keep operational failures inside the MCP result instead of crashing stdio."""
    @wraps(function)
    def wrapper(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except Exception as exc:
            message = str(exc)
            lowered = message.lower()
            if "backend service identity" in lowered or "defaultazurecredential" in lowered:
                message = "Backend service identity is not configured; interactive sign-in is disabled."
            elif "data source name not found" in lowered or "im002" in lowered:
                # Only the true missing-driver signature — every pyodbc error from this driver is
                # prefixed "[Microsoft][ODBC Driver 18 for SQL Server]", so matching that substring
                # alone mislabels real connection failures (timeout, auth, network) as "not installed".
                message = "Microsoft ODBC Driver 18 for SQL Server is not installed or registered."
            return json.dumps({"error": message, "data": []})
    return wrapper


@mcp.tool()
@safe_tool
def list_tables(schema: str | None = None) -> str:
    """List user tables and views, optionally filtered to one schema."""
    sql = """
        SELECT s.name AS SchemaName, o.name AS ObjectName,
               CASE o.type WHEN 'U' THEN 'TABLE' ELSE 'VIEW' END AS ObjectType
        FROM sys.objects o
        JOIN sys.schemas s ON s.schema_id = o.schema_id
        WHERE o.type IN ('U', 'V') AND o.is_ms_shipped = 0
          AND (? IS NULL OR s.name = ?)
        ORDER BY s.name, o.name
    """
    with connect() as connection:
        cursor = _cursor(connection)
        cursor.execute(sql, schema, schema)
        rows, _ = rows_as_dicts(cursor)
    return _result(rows, count=len(rows))


@mcp.tool()
@safe_tool
def get_table_schema(table: str, schema: str = "dbo") -> str:
    """Return columns, SQL data types, nullability, defaults, and key participation."""
    validate_identifier(schema, "schema")
    validate_identifier(table, "table")
    sql = """
        SELECT c.column_id AS Ordinal, c.name AS ColumnName, t.name AS DataType,
               CASE WHEN t.name IN ('nvarchar','nchar') AND c.max_length > 0 THEN c.max_length / 2
                    ELSE c.max_length END AS MaxLength,
               c.precision AS NumericPrecision, c.scale AS NumericScale,
               c.is_nullable AS IsNullable, dc.definition AS DefaultValue,
               CASE WHEN pk.column_id IS NULL THEN 0 ELSE 1 END AS IsPrimaryKey
        FROM sys.columns c
        JOIN sys.types t ON c.user_type_id = t.user_type_id
        JOIN sys.objects o ON c.object_id = o.object_id
        JOIN sys.schemas s ON o.schema_id = s.schema_id
        LEFT JOIN sys.default_constraints dc ON c.default_object_id = dc.object_id
        LEFT JOIN (
            SELECT ic.object_id, ic.column_id
            FROM sys.indexes i
            JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
            WHERE i.is_primary_key = 1
        ) pk ON pk.object_id = c.object_id AND pk.column_id = c.column_id
        WHERE s.name = ? AND o.name = ? AND o.type IN ('U','V')
        ORDER BY c.column_id
    """
    with connect() as connection:
        cursor = _cursor(connection)
        cursor.execute(sql, schema, table)
        rows, _ = rows_as_dicts(cursor)
    if not rows:
        raise ValueError(f"Table or view not found: {schema}.{table}")
    rows = [row for row in rows if not is_column_blocked(row["ColumnName"], table)]
    return _result(rows, schema=schema, table=table)


@mcp.tool()
@safe_tool
def get_relationships(schema: str = "dbo") -> str:
    """List foreign-key relationships for tables in a schema."""
    validate_identifier(schema, "schema")
    sql = """
        SELECT fk.name AS ConstraintName,
               ps.name AS ParentSchema, pt.name AS ParentTable, pc.name AS ParentColumn,
               rs.name AS ReferencedSchema, rt.name AS ReferencedTable, rc.name AS ReferencedColumn
        FROM sys.foreign_keys fk
        JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
        JOIN sys.tables pt ON fkc.parent_object_id = pt.object_id
        JOIN sys.schemas ps ON pt.schema_id = ps.schema_id
        JOIN sys.columns pc ON pc.object_id = pt.object_id AND pc.column_id = fkc.parent_column_id
        JOIN sys.tables rt ON fkc.referenced_object_id = rt.object_id
        JOIN sys.schemas rs ON rt.schema_id = rs.schema_id
        JOIN sys.columns rc ON rc.object_id = rt.object_id AND rc.column_id = fkc.referenced_column_id
        WHERE ps.name = ? OR rs.name = ?
        ORDER BY pt.name, fk.name, fkc.constraint_column_id
    """
    with connect() as connection:
        cursor = _cursor(connection)
        cursor.execute(sql, schema, schema)
        rows, _ = rows_as_dicts(cursor)
    return _result(rows, count=len(rows))


def _visible_column_names(connection, schema: str, table: str) -> list[str]:
    """All column names on a table, minus any blocked by SENSITIVE_COLUMNS."""
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT c.name FROM sys.columns c
        JOIN sys.objects o ON c.object_id = o.object_id
        JOIN sys.schemas s ON o.schema_id = s.schema_id
        WHERE s.name = ? AND o.name = ?
        ORDER BY c.column_id
        """,
        schema, table,
    )
    names = [row[0] for row in cursor.fetchall()]
    if not names:
        raise ValueError(f"Table or view not found: {table}")
    return [name for name in names if not is_column_blocked(name, table)]


@mcp.tool()
@safe_tool
def sample_rows(table: str, schema: str = "dbo", limit: int = 5) -> str:
    """Return up to 20 sample rows from one validated table or view."""
    validate_identifier(schema, "schema")
    validate_identifier(table, "table")
    limit = max(1, min(int(limit), 20))
    with connect() as connection:
        columns = _visible_column_names(connection, schema, table)
        if not columns:
            raise ValueError(f"No visible columns on {table} — every column is restricted")
        column_list = ", ".join(f"[{name}]" for name in columns)
        sql = f"SELECT TOP ({limit}) {column_list} FROM [{schema}].[{table}]"
        cursor = _cursor(connection)
        cursor.execute(sql)
        rows, truncated = rows_as_dicts(cursor, limit)
    return _result(rows, count=len(rows), truncated=truncated)


@mcp.tool()
@safe_tool
def execute_readonly_query(query: str) -> str:
    """Execute one validated SELECT/WITH query with a 30-second timeout and 500-row cap."""
    query = validate_readonly_sql(query)
    with connect() as connection:
        cursor = _cursor(connection)
        cursor.execute(query)
        if cursor.description is None:
            raise ValueError("The query did not return a result set")
        rows, truncated = rows_as_dicts(cursor, MAX_ROWS)
    return _result(rows, count=len(rows), truncated=truncated, maxRows=MAX_ROWS)


@mcp.tool()
@safe_tool
def render_chart(query: str, code: str) -> str:
    """Run a validated read-only query and render a matplotlib chart of its result as a PNG image.

    `query` is validated and executed exactly like execute_readonly_query — the same read-only,
    column-restriction, and row-cap rules apply, and it runs independently of any earlier query in
    this conversation (write the full query here, don't assume prior context).

    `code` is plain Python plotting code, executed in an isolated environment with only `pd`
    (pandas) and `plt` (matplotlib.pyplot) available and a DataFrame named `df` already holding the
    query's real rows. Do not redefine df. Do not import anything — pd and plt are already provided.
    Assign the finished chart to a variable named `fig` (e.g. `fig, ax = plt.subplots()`). No file
    or network access is available.
    """
    validated_query = validate_readonly_sql(query)
    with connect() as connection:
        cursor = _cursor(connection)
        cursor.execute(validated_query)
        if cursor.description is None:
            raise ValueError("The query did not return a result set")
        rows, _ = rows_as_dicts(cursor, MAX_ROWS)
    if not rows:
        raise ValueError("The query returned no rows — nothing to chart")
    image_bytes = render_chart_image(rows, code)
    return _result(None, count=len(rows), image_base64=base64.b64encode(image_bytes).decode("ascii"))


if __name__ == "__main__":
    mcp.run(transport="stdio")
