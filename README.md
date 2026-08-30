# InsightFlow AI

A text-to-SQL business-intelligence agent: ask a question in plain English, and it converts the question to SQL, runs it read-only against the database, and answers in text. Built with a LangChain tool-calling agent on Microsoft Foundry, backed by an MCP server that owns all schema discovery and query execution. It runs immediately in a self-contained demo mode, then switches to Microsoft Foundry and Azure SQL when production configuration is ready. There is no Next.js, FastAPI, Azure Functions, or interactive end-user sign-in.

## Run it now

```bash
.venv/bin/streamlit run streamlit_app.py
```

Open `http://localhost:8501`. With the default `APP_MODE=auto`, incomplete Azure configuration selects demo mode automatically. Demo mode creates a deterministic 5,000-row SQLite star schema in `data/`, exposes it through the same MCP tools, and uses a local deterministic BI analyst for chat. It does not pretend that demo results came from Azure.

## Architecture

```text
Streamlit UI
    |
    | user question + chat history
    v
LangChain tool-calling agent (Foundry model) or local demo analyst
    |
    | tool calls, using MCP-discovered JSON schemas (langchain-mcp-adapters)
    v
InsightFlow MCP server (stdio subprocess)
    |
    | metadata calls, or one SQLGlot-validated SELECT/WITH
    v
Azure SQL or demo SQLite
```

The model has no database credentials and cannot connect directly to SQL. The agent writes SQL as part of its own reasoning (`list_tables` / `get_table_schema` / `get_relationships` to learn the schema, `execute_readonly_query` to run it), but the MCP server is what actually owns database access and enforces validation, timeouts, result limits, identifier checks, and read-only behavior. Both runtime modes use the same MCP interface, so the guardrails apply identically whether the caller is the LangChain agent or the deterministic demo analyst.

## Runtime modes

| `APP_MODE` | Behavior |
|---|---|
| `auto` | Uses Azure only when SQL, ODBC, Foundry, and service identity are all ready; otherwise uses demo mode. |
| `demo` | Always uses seeded SQLite and the deterministic local MCP analyst. No credentials are needed. |
| `azure` | Requires Foundry, Azure SQL, Driver 18, and unattended credentials; configuration failures are surfaced immediately. |

## MCP tools

| Tool | Purpose |
|---|---|
| `list_tables` | List user tables and views, optionally by schema. |
| `get_table_schema` | Return columns, types, nullability, defaults, and primary keys. |
| `get_relationships` | Return foreign-key relationships. |
| `sample_rows` | Return at most 20 rows from a validated table name. |
| `execute_readonly_query` | Execute one SQLGlot-validated SELECT/WITH query with a 30-second timeout and 500-row cap. |

## Security model

- No interactive browser login is enabled.
- Credentials stay in `.env`, which Git ignores. SQL credentials are passed only to the local MCP subprocess; Foundry credentials are used only in the main Streamlit process, never by MCP.
- A Microsoft Entra service principal is one valid option for Foundry and/or Azure SQL, but not required — API-key auth (Foundry) and a SQL login (Azure SQL) are equally supported and avoid needing Entra ID app-registration permissions.
- If SQL authentication is used, create a dedicated login mapped only to `db_datareader`.
- The SQL principal must not have write, DDL, owner, or server-level permissions.
- SQLGlot rejects mutations, multiple statements, cross-database references, system catalog queries, external data access, and executable procedures.
- Optional column-level restriction: set `SENSITIVE_COLUMNS` (comma-separated `ColumnName` or `Table.ColumnName`) in `.env` to hide specific columns from the agent entirely — `get_table_schema`/`sample_rows` never return them, and `execute_readonly_query` rejects any query referencing them (including via `SELECT *` or a table alias). See `insightflow/sql.py`.
- The agent refuses to answer a question that produced zero MCP tool calls — it has no source of information beyond this database, so an ungrounded answer is treated as a bug, not a fallback. See `AGENT_INSTRUCTIONS` and the trace check in `ask_foundry_agent()` (`insightflow/agent.py`).
- The database permission boundary remains the final control; application validation is defense in depth. For a genuinely sensitive column, prefer a DB-native control too (Azure SQL column-level `DENY` or Dynamic Data Masking) — the app-level guard above only protects what already goes through this app's MCP server.

For production, run Streamlit and the MCP server under managed identity in Azure Container Apps or another managed compute service. If MCP is moved from stdio to Streamable HTTP, put it behind private networking and OAuth rather than exposing an unauthenticated endpoint.

## Repository map

```text
streamlit_app.py             Streamlit chat, readiness UI, and database explorer
insightflow/agent.py         LangChain tool-calling agent (Foundry model + MCP tools) and demo analyst
insightflow/mcp_server.py    MCP server: schema discovery and guarded SQL execution
insightflow/sql.py           connection, serialization, and SQL guardrails
insightflow/config.py        environment loading and MCP subprocess/stdio config
insightflow/demo_db.py       deterministic local star-schema generator
database/schema.sql          Azure SQL star schema
database/seed.sql            deterministic sample data
tests/test_sql_guard.py      SQL safety tests
```

## Layout

The app is three tabs: **Chat**, **Dashboard**, and **MCP Explorer**. The sidebar holds mode
status and "New conversation" — schema browsing lives in its own tab instead of cluttering the
sidebar.

## Dashboards

Two independent visualizations:

- **Dashboard tab**: a standing overview — KPI tiles (revenue, profit, units, orders, customers),
  top products by revenue, revenue by state, and a monthly revenue trend — computed directly from
  fixed queries (`_dashboard_queries()` in `streamlit_app.py`, cached 5 minutes via
  `st.cache_data`) independent of chat. The query text differs between demo (SQLite) and Azure
  (T-SQL) syntax but returns the same shape either way.
- **Chat tab**: every answer also visualizes the result of its last `execute_readonly_query` call,
  chosen automatically by shape:

  | Result shape | Rendered as |
  |---|---|
  | One row of numeric columns | A KPI row (`st.metric` tiles) |
  | Multiple rows, one label column + one numeric column (ID-like columns ignored), ≤20 rows | A single-hue ranking bar chart (or a line chart if the label column is date-like) |
  | Anything else | A plain table |

  The raw rows are always available underneath in a "Result data" expander. Implemented in
  `AgentAnswer.rows` (`insightflow/agent.py`) and `render_result_view()` (`streamlit_app.py`).

## Azure-mode prerequisites

- Native Python 3.11+
- Microsoft ODBC Driver 18 for SQL Server
- Azure SQL Database reachable from this machine
- Microsoft Foundry project and deployed model
- Non-interactive backend credentials

On Apple Silicon, verify the native architecture and registered driver:

```bash
python3.11 -c "import platform; print(platform.machine())"
odbcinst -q -d
```

Expected values are `arm64` and `ODBC Driver 18 for SQL Server`.

## Configuration

Demo mode requires no configuration. For Azure mode, create the local configuration:

```bash
cp .env.example .env
```

Each of Foundry and Azure SQL supports two independent authentication paths — pick whichever you have permission for.

**Foundry:**

- **API key** (no Entra ID app registration needed — works even without permission to register apps, e.g. on a restricted school/org tenant): on your Foundry resource's overview page, copy the **API key** and the **Azure OpenAI endpoint**, and set:
  ```text
  AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
  AZURE_OPENAI_API_KEY=...
  ```
- **Microsoft Entra service principal** (requires permission to create an app registration in your tenant):
  ```text
  AZURE_TENANT_ID=...
  AZURE_CLIENT_ID=...
  AZURE_CLIENT_SECRET=...
  FOUNDRY_PROJECT_ENDPOINT=...
  ```
  Also grant the service principal the **Foundry User** role (recently renamed from "Azure AI User") on the Foundry project via Access control (IAM) — this is not granted automatically for service principals.

**Azure SQL:**

- **SQL login** (no Entra ID needed): configure `AZURE_SQL_USERNAME` and `AZURE_SQL_PASSWORD` for a dedicated read-only login. Do not use a database owner account. Create it once as the server admin:
  ```sql
  CREATE LOGIN insightflow_reader WITH PASSWORD = 'a-strong-password';
  CREATE USER insightflow_reader FOR LOGIN insightflow_reader;
  ALTER ROLE db_datareader ADD MEMBER insightflow_reader;
  ```
- **Microsoft Entra service principal** (the same one used for Foundry, if using that path): connect as the Microsoft Entra database administrator once and grant minimum access:
  ```sql
  CREATE USER [your-service-principal-name] FROM EXTERNAL PROVIDER;
  ALTER ROLE db_datareader ADD MEMBER [your-service-principal-name];
  ```

## Database setup

Run these scripts against the target Azure SQL database in order:

1. `database/schema.sql`
2. `database/seed.sql`

The seed script is idempotent and creates 5,000 sample sales records.

## Install and run

```bash
/opt/homebrew/bin/python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/streamlit run streamlit_app.py
```

Open `http://localhost:8501`. Streamlit launches the MCP server automatically over stdio for each operation; no separate MCP terminal is required.

## Test

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -c "import asyncio; from insightflow.agent import discover_tools; print(asyncio.run(discover_tools()))"
```

## Typical agent execution

For “Which five products generated the most profit in Florida this quarter?” the model should:

1. Call `list_tables`.
2. Call `get_table_schema` for relevant fact and dimension tables.
3. Call `get_relationships` to verify joins.
4. Submit one aggregate query through `execute_readonly_query`.
5. Explain the verified result, filters, time window, and caveats.

MCP activity is visible in Streamlit expanders, giving developers and analysts an audit trail of every tool call and returned result.
