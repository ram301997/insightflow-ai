import os
import sys
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


AZURE_ENV_KEYS = (
    "AZURE_SQL_SERVER",
    "AZURE_SQL_DATABASE",
    "AZURE_SQL_USERNAME",
    "AZURE_SQL_PASSWORD",
    "AZURE_TENANT_ID",
    "AZURE_CLIENT_ID",
    "AZURE_CLIENT_SECRET",
    "FOUNDRY_PROJECT_ENDPOINT",
    "FOUNDRY_MODEL",
    "SENSITIVE_COLUMNS",
)


def configured(name: str) -> bool:
    value = os.getenv(name, "").strip()
    return bool(value) and "YOUR" not in value.upper()


def service_identity_ready() -> bool:
    return all(configured(name) for name in ("AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET"))


def foundry_api_key_ready() -> bool:
    """API-key auth for a direct Azure OpenAI endpoint — no Entra ID app registration needed."""
    return configured("AZURE_OPENAI_ENDPOINT") and configured("AZURE_OPENAI_API_KEY")


def foundry_ready() -> bool:
    if not configured("FOUNDRY_MODEL"):
        return False
    if foundry_api_key_ready():
        return True
    return configured("FOUNDRY_PROJECT_ENDPOINT") and service_identity_ready()


def azure_sql_ready() -> bool:
    import pyodbc

    target = configured("AZURE_SQL_SERVER") and configured("AZURE_SQL_DATABASE")
    sql_login = configured("AZURE_SQL_USERNAME") and configured("AZURE_SQL_PASSWORD")
    driver = "ODBC Driver 18 for SQL Server" in pyodbc.drivers()
    return target and driver and (sql_login or service_identity_ready())


def require(*names: str) -> None:
    missing = [name for name in names if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"Missing configuration: {', '.join(missing)}")


def azure_credential():
    """Return only unattended credentials; never fall back to interactive developer auth."""
    from azure.identity import ClientSecretCredential, ManagedIdentityCredential

    tenant_id = os.getenv("AZURE_TENANT_ID")
    client_id = os.getenv("AZURE_CLIENT_ID")
    client_secret = os.getenv("AZURE_CLIENT_SECRET")
    if tenant_id and client_id and client_secret:
        return ClientSecretCredential(tenant_id, client_id, client_secret)
    if os.getenv("IDENTITY_ENDPOINT") or os.getenv("MSI_ENDPOINT") or os.getenv("WEBSITE_HOSTNAME"):
        return ManagedIdentityCredential(client_id=client_id or None)
    raise RuntimeError(
        "Backend service identity is not configured. Set AZURE_TENANT_ID, "
        "AZURE_CLIENT_ID, and AZURE_CLIENT_SECRET in .env."
    )


def _mcp_child_env() -> dict[str, str]:
    """Explicitly pass only required values to the MCP server subprocess."""
    child_env = {key: os.environ[key] for key in AZURE_ENV_KEYS if os.getenv(key)}
    child_env["PATH"] = os.environ.get("PATH", "")
    child_env["PYTHONPATH"] = str(ROOT)
    return child_env


def mcp_server_parameters():
    """Stdio settings for the raw MCP client (database explorer)."""
    from mcp import StdioServerParameters

    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "insightflow.mcp_server"],
        cwd=str(ROOT),
        env=_mcp_child_env(),
    )


def mcp_stdio_connection() -> dict:
    """Stdio connection for langchain-mcp-adapters, used by the LangChain agent."""
    return {
        "transport": "stdio",
        "command": sys.executable,
        "args": ["-m", "insightflow.mcp_server"],
        "cwd": str(ROOT),
        "env": _mcp_child_env(),
    }
