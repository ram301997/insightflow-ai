import asyncio
import json
import os

import pandas as pd
import pyodbc
import streamlit as st
from langchain_core.messages import AIMessage, HumanMessage

from insightflow.agent import ask_foundry_agent, call_mcp_tool, discover_tools
from insightflow.config import foundry_api_key_ready


st.set_page_config(page_title="InsightFlow AI", page_icon="📊", layout="wide")

ACCENT = "#6366F1"
ACCENT_DARK = "#4338CA"
CHART_COLOR = "#6366F1"
INK = "#1E1B2E"
SURFACE = "#FFFFFF"
SURFACE_MUTED = "#F7F7FB"
BORDER = "rgba(30, 27, 46, 0.08)"

st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"] {{
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }}

    [data-testid="stAppViewContainer"] {{
        background: linear-gradient(180deg, #FAFAFE 0%, #F4F4FB 100%);
    }}

    /* ---- Header ---- */
    .if-hero {{
        display: flex;
        align-items: center;
        gap: 0.85rem;
        padding: 0.25rem 0 1.1rem 0;
    }}
    .if-hero-badge {{
        width: 46px;
        height: 46px;
        border-radius: 13px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.4rem;
        background: linear-gradient(135deg, {ACCENT} 0%, {ACCENT_DARK} 100%);
        box-shadow: 0 6px 16px rgba(99, 102, 241, 0.28);
    }}
    .if-hero-title {{
        font-size: 1.55rem;
        font-weight: 800;
        color: {INK};
        letter-spacing: -0.02em;
        line-height: 1.15;
    }}
    .if-hero-subtitle {{
        font-size: 0.92rem;
        color: rgba(30, 27, 46, 0.55);
        font-weight: 500;
    }}

    /* ---- Tabs ---- */
    [data-testid="stTabs"] [data-baseweb="tab-list"] {{
        gap: 0.35rem;
        border-bottom: 1px solid {BORDER};
    }}
    [data-testid="stTab"] {{
        font-size: 0.95rem;
        font-weight: 600;
        padding: 0.65rem 1.3rem;
        color: rgba(30, 27, 46, 0.55);
        border-radius: 10px 10px 0 0;
    }}
    [data-testid="stTab"][aria-selected="true"] {{
        color: {ACCENT_DARK};
        background: rgba(99, 102, 241, 0.08);
    }}

    /* ---- Metrics ---- */
    [data-testid="stMetric"] {{
        background: {SURFACE};
        border: 1px solid {BORDER};
        border-radius: 14px;
        padding: 1.1rem 1.1rem 0.85rem 1.1rem;
        box-shadow: 0 1px 3px rgba(30, 27, 46, 0.04);
    }}
    [data-testid="stMetricValue"] {{
        font-size: 1.35rem;
        font-weight: 700;
        color: {INK};
        white-space: normal;
        overflow-wrap: break-word;
        line-height: 1.25;
    }}
    [data-testid="stMetricLabel"] {{
        font-weight: 600;
        text-transform: uppercase;
        font-size: 0.7rem;
        letter-spacing: 0.05em;
        color: rgba(30, 27, 46, 0.5);
    }}

    /* ---- Chat bubbles ---- */
    [data-testid="stChatMessage"] {{
        border-radius: 18px;
        padding: 0.9rem 1.1rem;
        margin-bottom: 0.65rem;
        border: 1px solid transparent;
        box-shadow: 0 1px 2px rgba(30, 27, 46, 0.03);
    }}
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {{
        background: linear-gradient(135deg, {ACCENT} 0%, {ACCENT_DARK} 100%);
        color: #FFFFFF;
        margin-left: 8%;
    }}
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) p {{
        color: #FFFFFF;
    }}
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stChatMessageAvatarUser"] {{
        background: rgba(255, 255, 255, 0.22);
    }}
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {{
        background: {SURFACE};
        border-color: {BORDER};
        margin-right: 8%;
    }}
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) [data-testid="stChatMessageAvatarAssistant"] {{
        background: linear-gradient(135deg, {ACCENT} 0%, {ACCENT_DARK} 100%);
        color: #FFFFFF;
    }}
    [data-testid="stChatMessageContent"] h1, [data-testid="stChatMessageContent"] h2 {{
        font-size: 1.05rem;
        margin-top: 0;
        margin-bottom: 0.4rem;
    }}
    /* The agent occasionally backtick-wraps a plain number; don't let it read as a code artifact. */
    [data-testid="stChatMessageContent"] code {{
        background: transparent;
        color: inherit;
        font-family: inherit;
        font-size: inherit;
        padding: 0;
    }}

    [data-testid="stChatInput"] {{
        border-radius: 14px;
    }}

    /* ---- Buttons ---- */
    .stButton > button {{
        border-radius: 10px;
        font-weight: 600;
    }}
    .stButton > button[kind="primary"] {{
        background: linear-gradient(135deg, {ACCENT} 0%, {ACCENT_DARK} 100%);
        border: none;
    }}

    /* ---- Containers / cards ---- */
    [data-testid="stVerticalBlockBorderWrapper"] {{
        border-radius: 14px !important;
        border-color: {BORDER} !important;
    }}

    /* ---- Sidebar ---- */
    [data-testid="stSidebar"] {{
        background: {SURFACE_MUTED};
        border-right: 1px solid {BORDER};
    }}
    </style>
    """,
    unsafe_allow_html=True,
)


def configured(name: str) -> bool:
    value = os.getenv(name, "").strip()
    return bool(value) and "YOUR" not in value.upper()


driver_ready = "ODBC Driver 18 for SQL Server" in pyodbc.drivers()
sql_target_ready = configured("AZURE_SQL_SERVER") and configured("AZURE_SQL_DATABASE")
service_identity_ready = all(
    configured(name) for name in ("AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET")
)
sql_login_ready = configured("AZURE_SQL_USERNAME") and configured("AZURE_SQL_PASSWORD")
sql_ready = driver_ready and sql_target_ready and (service_identity_ready or sql_login_ready)
foundry_key_ready = foundry_api_key_ready()
foundry_ready = configured("FOUNDRY_MODEL") and (
    foundry_key_ready or (configured("FOUNDRY_PROJECT_ENDPOINT") and service_identity_ready)
)
agent_ready = sql_ready and foundry_ready


def run(coro):
    return asyncio.run(coro)


def show_tool_result(result):
    if isinstance(result, dict) and result.get("error"):
        st.error(result["error"])
        return
    data = result.get("data") if isinstance(result, dict) else result
    if isinstance(data, list):
        st.dataframe(pd.DataFrame(data), width="stretch", hide_index=True)
    else:
        st.json(result)


MAX_CHART_ROWS = 20


def _is_date_like(series: pd.Series) -> bool:
    if pd.api.types.is_numeric_dtype(series):
        return False
    try:
        pd.to_datetime(series, errors="raise")
        return True
    except (ValueError, TypeError):
        return False


def _is_id_column(name: str) -> bool:
    """Identifier columns (e.g. ProductId) are structural, not a metric or a label worth charting."""
    lowered = name.lower()
    return lowered == "id" or lowered.endswith("id")


CHART_TYPES = {"bar", "line", "metric", "table"}


def _render_metric_row(df: pd.DataFrame, numeric_cols: list[str]) -> None:
    metric_cols = st.columns(min(len(numeric_cols), 4))
    for index, name in enumerate(numeric_cols[:8]):
        value = df[name].iloc[0]  # per-column access preserves that column's own dtype
        formatted = f"{value:,.2f}" if pd.api.types.is_float_dtype(df[name]) else f"{value:,}"
        metric_cols[index % len(metric_cols)].metric(name, formatted)


def _valid_chart_spec(spec: dict | None, df: pd.DataFrame) -> dict | None:
    """Trust the agent's own suggest_visualization call only when it's structurally consistent
    with the actual result — a spec naming a column that isn't there, or "metric" on a multi-row
    result, falls back to the shape heuristic instead of erroring or rendering nothing."""
    if not spec or spec.get("chart_type") not in CHART_TYPES:
        return None
    chart_type = spec["chart_type"]
    if chart_type in ("bar", "line"):
        x_column, y_column = spec.get("x_column"), spec.get("y_column")
        if x_column not in df.columns or y_column not in df.columns:
            return None
        if not pd.api.types.is_numeric_dtype(df[y_column]):
            return None
    elif chart_type == "metric":
        numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c]) and not _is_id_column(c)]
        if len(df) != 1 or not numeric_cols:
            return None
    return spec


def render_result_view(rows: list[dict] | None, chart_spec: dict | None = None) -> None:
    """Render the last query's result as a KPI row, a chart, or a table.

    Prefers the agent's own suggest_visualization call — grounded in what the question actually
    asked, not just the data's shape — when it's consistent with the real result; falls back to a
    shape-based heuristic otherwise (no chart_spec, or the agent skipped the call).
    """
    if not rows:
        return
    df = pd.DataFrame(rows)
    spec = _valid_chart_spec(chart_spec, df)

    if spec:
        chart_type = spec["chart_type"]
        if chart_type == "metric":
            numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c]) and not _is_id_column(c)]
            _render_metric_row(df, numeric_cols)
            with st.expander("Result data"):
                st.dataframe(df, width="stretch", hide_index=True)
        elif chart_type == "table":
            st.dataframe(df, width="stretch", hide_index=True)
        else:
            x_column, y_column = spec["x_column"], spec["y_column"]
            if chart_type == "line":
                st.line_chart(df.sort_values(x_column), x=x_column, y=y_column, color=CHART_COLOR)
            else:
                st.bar_chart(
                    df.sort_values(y_column), x=x_column, y=y_column,
                    color=CHART_COLOR, horizontal=True, sort=False,
                )
            with st.expander("Result data"):
                st.dataframe(df, width="stretch", hide_index=True)
        return

    chartable = [c for c in df.columns if not _is_id_column(c)]
    numeric_cols = [c for c in chartable if pd.api.types.is_numeric_dtype(df[c])]
    other_cols = [c for c in chartable if c not in numeric_cols]

    if len(df) == 1 and numeric_cols:
        _render_metric_row(df, numeric_cols)
        with st.expander("Result data"):
            st.dataframe(df, width="stretch", hide_index=True)
    elif len(other_cols) == 1 and len(numeric_cols) == 1 and 1 < len(df) <= MAX_CHART_ROWS:
        label_col, value_col = other_cols[0], numeric_cols[0]
        if _is_date_like(df[label_col]):
            st.line_chart(df.sort_values(label_col), x=label_col, y=value_col, color=CHART_COLOR)
        else:
            st.bar_chart(
                df.sort_values(value_col), x=label_col, y=value_col, color=CHART_COLOR, horizontal=True, sort=False
            )
        with st.expander("Result data"):
            st.dataframe(df, width="stretch", hide_index=True)
    else:
        st.dataframe(df, width="stretch", hide_index=True)


def friendly_error(exc: Exception) -> str:
    message = str(exc)
    lowered = message.lower()
    if "defaultazurecredential failed" in lowered:
        return (
            "The backend service identity is not configured. Interactive sign-in is disabled; "
            "set the service-principal variables in .env."
        )
    if "data source name not found" in lowered or "im002" in lowered:
        return "Microsoft ODBC Driver 18 for SQL Server is not installed or registered."
    if "login timeout expired" in lowered or "could not open a connection" in lowered:
        return (
            "Could not reach the Azure SQL server. Check AZURE_SQL_SERVER/AZURE_SQL_DATABASE in "
            f".env and that this machine's IP is allowed through the server's firewall. ({message})"
        )
    if "login failed for user" in lowered:
        return f"Azure SQL rejected the credentials in .env (AZURE_SQL_USERNAME/AZURE_SQL_PASSWORD). ({message})"
    return message


DASHBOARD_QUERIES = {
    "kpis": """
        SELECT ROUND(SUM(Revenue),2) AS TotalRevenue, ROUND(SUM(Profit),2) AS TotalProfit,
               SUM(Quantity) AS TotalUnits, COUNT(DISTINCT SaleId) AS TotalOrders,
               COUNT(DISTINCT CustomerId) AS TotalCustomers
        FROM dbo.FactSales
    """,
    "top_products": """
        SELECT TOP 5 p.ProductName, ROUND(SUM(fs.Revenue),2) AS Revenue
        FROM dbo.FactSales fs JOIN dbo.DimProduct p ON p.ProductId = fs.ProductId
        GROUP BY p.ProductName ORDER BY Revenue DESC
    """,
    "by_state": """
        SELECT s.State, ROUND(SUM(fs.Revenue),2) AS Revenue
        FROM dbo.FactSales fs JOIN dbo.DimStore s ON s.StoreId = fs.StoreId
        GROUP BY s.State ORDER BY Revenue DESC
    """,
    "trend": """
        SELECT CONCAT(d.YearNumber, '-', RIGHT('0' + CAST(d.MonthNumber AS VARCHAR(2)), 2)) AS Month,
               ROUND(SUM(fs.Revenue),2) AS Revenue
        FROM dbo.FactSales fs JOIN dbo.DimDate d ON d.DateId = fs.DateId
        GROUP BY d.YearNumber, d.MonthNumber ORDER BY d.YearNumber, d.MonthNumber
    """,
}


@st.cache_data(ttl=300, show_spinner="Loading dashboard…")
def load_dashboard() -> dict[str, list[dict]]:
    data = {}
    for name, query in DASHBOARD_QUERIES.items():
        result = run(call_mcp_tool("execute_readonly_query", {"query": query}))
        data[name] = result.get("data", [])
    return data


if "messages" not in st.session_state:
    st.session_state.messages = []


with st.sidebar:
    st.markdown(
        """
        <div style="display:flex; align-items:center; gap:0.6rem; padding:0.2rem 0 1.1rem 0;">
            <div style="width:34px; height:34px; border-radius:10px; display:flex; align-items:center;
                        justify-content:center; font-size:1.1rem; background:linear-gradient(135deg,#6366F1,#4338CA);">
                📊
            </div>
            <div style="font-weight:800; font-size:1.05rem; color:#1E1B2E; letter-spacing:-0.01em;">
                InsightFlow AI
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    status_label = "Connected to Azure SQL" if agent_ready else "Setup needed"
    status_color = "#1a7f4f" if agent_ready else "#b45309"
    status_bg = "rgba(26,127,79,0.1)" if agent_ready else "rgba(180,83,9,0.1)"
    st.markdown(
        f"""
        <div style="display:inline-flex; align-items:center; gap:0.4rem; background:{status_bg};
                    color:{status_color}; font-weight:600; font-size:0.78rem; padding:0.3rem 0.7rem;
                    border-radius:999px; margin-bottom:1.1rem;">
            ● {status_label}
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button("＋ New conversation", width="stretch"):
        st.session_state.messages = []
        st.rerun()

    with st.expander("System status"):
        st.write("✅ Streamlit and local MCP")
        st.write(f"{'✅' if driver_ready else '❌'} Microsoft ODBC Driver 18")
        st.write(f"{'✅' if sql_target_ready else '❌'} Azure SQL server and database")
        st.write(f"{'✅' if (service_identity_ready or sql_login_ready) else '❌'} Non-interactive SQL identity")
        st.write(f"{'✅' if configured('FOUNDRY_MODEL') else '❌'} Foundry model deployment")
        if foundry_key_ready:
            st.write("✅ Foundry auth: API key + endpoint")
        else:
            st.write(f"{'✅' if configured('FOUNDRY_PROJECT_ENDPOINT') else '❌'} Foundry auth: project endpoint")
            st.write(f"{'✅' if service_identity_ready else '❌'} Foundry auth: service principal")


st.markdown(
    """
    <div class="if-hero">
        <div class="if-hero-badge">📊</div>
        <div>
            <div class="if-hero-title">InsightFlow AI</div>
            <div class="if-hero-subtitle">Ask business questions in plain English, or browse the overview below.</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

tab_chat, tab_dashboard, tab_explorer = st.tabs(["💬 Chat", "📊 Dashboard", "🛠️ MCP Explorer"])


with tab_chat:
    for index, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            render_result_view(message.get("rows"), message.get("chart_spec"))
            if message.get("trace"):
                with st.expander(f"Agent activity ({len(message['trace'])} calls)"):
                    for call_index, call in enumerate(message["trace"], start=1):
                        st.markdown(f"**{call_index}. `{call['tool']}`**")
                        st.code(json.dumps(call["arguments"], indent=2), language="json")
                        if call["is_error"]:
                            st.error(call["result"])
                        else:
                            st.code(call["result"], language="json")

    clicked_example = None
    if not st.session_state.messages and agent_ready:
        example_questions = [
            "Top 5 products by profit in Florida this quarter",
            "Which products have the thinnest margins?",
            "Revenue by state this year",
        ]
        st.caption("Try one of these, or ask your own:")
        example_cols = st.columns(len(example_questions))
        for col, example in zip(example_cols, example_questions):
            if col.button(example, width="stretch"):
                clicked_example = example

    question = st.chat_input(
        "Example: Which five products generated the most profit in Florida this quarter?",
        disabled=not agent_ready,
    ) or clicked_example

    # Guard against a duplicate submission (e.g. a double-click on an example button)
    # landing as two separate reruns before the first one's answer is appended.
    already_pending = bool(
        question
        and st.session_state.messages
        and st.session_state.messages[-1]["role"] == "user"
        and st.session_state.messages[-1]["content"] == question
    )
    if question and already_pending:
        question = None

    if question:
        history = [
            AIMessage(content=message["content"]) if message["role"] == "assistant" else HumanMessage(content=message["content"])
            for message in st.session_state.messages
        ]
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            answer = None
            error_message = None
            with st.status("Inspecting Azure SQL through MCP…", expanded=True) as status:
                try:
                    answer = run(ask_foundry_agent(question, history=history))
                    status.update(label="Analysis complete", state="complete", expanded=False)
                except Exception as exc:
                    status.update(label="Request failed", state="error", expanded=False)
                    error_message = friendly_error(exc)

            if answer is not None:
                st.markdown(answer.text)
                render_result_view(answer.rows, answer.chart_spec)
                if answer.trace:
                    with st.expander(f"Agent activity ({len(answer.trace)} calls)"):
                        for index, call in enumerate(answer.trace, start=1):
                            st.markdown(f"**{index}. `{call['tool']}`**")
                            st.code(json.dumps(call["arguments"], indent=2), language="json")
                            st.code(call["result"], language="json")
                st.session_state.messages.append(
                    {
                        "role": "assistant", "content": answer.text, "trace": answer.trace,
                        "rows": answer.rows, "chart_spec": answer.chart_spec,
                    }
                )
            else:
                st.error(error_message)
                st.session_state.messages.append({"role": "assistant", "content": f"Error: {error_message}"})


with tab_dashboard:
    if not sql_ready:
        st.info("Configure Azure SQL credentials in .env to see the overview — see the sidebar's System status.")
    else:
        try:
            dashboard_data = load_dashboard()
        except Exception as exc:
            dashboard_data = None
            st.error(friendly_error(exc))

        if dashboard_data:
            kpi_row = dashboard_data["kpis"][0] if dashboard_data["kpis"] else {}
            metrics = [
                ("Revenue", "TotalRevenue", "${:,.0f}"),
                ("Profit", "TotalProfit", "${:,.0f}"),
                ("Units sold", "TotalUnits", "{:,.0f}"),
                ("Orders", "TotalOrders", "{:,.0f}"),
                ("Customers", "TotalCustomers", "{:,.0f}"),
            ]
            kpi_cols = st.columns(5)
            for col, (label, key, fmt) in zip(kpi_cols, metrics):
                col.metric(label, fmt.format(kpi_row.get(key) or 0))

            st.write("")
            chart_col1, chart_col2 = st.columns(2)
            with chart_col1:
                with st.container(border=True):
                    st.markdown("**Top products by revenue**")
                    products_df = pd.DataFrame(dashboard_data["top_products"])
                    if not products_df.empty:
                        st.bar_chart(
                            products_df.sort_values("Revenue"),
                            x="ProductName", y="Revenue", color=CHART_COLOR, horizontal=True,
                        )
            with chart_col2:
                with st.container(border=True):
                    st.markdown("**Revenue by state**")
                    state_df = pd.DataFrame(dashboard_data["by_state"])
                    if not state_df.empty:
                        st.bar_chart(
                            state_df.sort_values("Revenue"),
                            x="State", y="Revenue", color=CHART_COLOR, horizontal=True,
                        )

            with st.container(border=True):
                st.markdown("**Revenue trend by month**")
                trend_df = pd.DataFrame(dashboard_data["trend"])
                if not trend_df.empty:
                    st.line_chart(trend_df, x="Month", y="Revenue", color=CHART_COLOR)

            if st.button("🔄 Refresh"):
                load_dashboard.clear()
                st.rerun()


with tab_explorer:
    st.caption("Inspect the live schema directly through the same MCP tools the agent uses.")

    schema_name = st.text_input("Schema", value="dbo")

    explorer_cols = st.columns(2)
    with explorer_cols[0]:
        with st.container(border=True):
            if st.button("List tables and views", width="stretch", disabled=not sql_ready):
                try:
                    st.session_state.explorer_result = run(call_mcp_tool("list_tables"))
                except Exception as exc:
                    st.session_state.explorer_result = {"error": friendly_error(exc)}
            if st.button("Relationships", width="stretch", disabled=not sql_ready):
                try:
                    st.session_state.explorer_result = run(
                        call_mcp_tool("get_relationships", {"schema": schema_name})
                    )
                except Exception as exc:
                    st.session_state.explorer_result = {"error": friendly_error(exc)}

    with explorer_cols[1]:
        with st.container(border=True):
            st.caption("Look up one table")
            table_name = st.text_input("Table name")
            col1, col2 = st.columns(2)
            if col1.button("Get schema", width="stretch", disabled=(not table_name or not sql_ready)):
                try:
                    st.session_state.explorer_result = run(
                        call_mcp_tool("get_table_schema", {"schema": schema_name, "table": table_name})
                    )
                except Exception as exc:
                    st.session_state.explorer_result = {"error": friendly_error(exc)}
            if col2.button("Sample rows", width="stretch", disabled=(not table_name or not sql_ready)):
                try:
                    st.session_state.explorer_result = run(
                        call_mcp_tool("sample_rows", {"schema": schema_name, "table": table_name, "limit": 5})
                    )
                except Exception as exc:
                    st.session_state.explorer_result = {"error": friendly_error(exc)}

    if "explorer_result" in st.session_state:
        with st.expander("Explorer result", expanded=True):
            show_tool_result(st.session_state.explorer_result)

    with st.expander("Available MCP tools"):
        try:
            for tool in run(discover_tools()):
                st.markdown(f"**{tool['name']}**  \n{tool['description']}")
        except Exception as exc:
            st.error(friendly_error(exc))
