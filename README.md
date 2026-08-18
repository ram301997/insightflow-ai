# InsightFlow AI

Azure-first conversational business intelligence starter.

## Architecture

- Azure Static Web Apps: Next.js frontend
- Azure Functions: Python API
- Microsoft Foundry: agent and model runtime
- Azure SQL Database: analytics data
- Managed Identity: passwordless Azure SQL and Foundry authentication
- Azure Key Vault: application secrets when needed
- Application Insights: observability
- Power BI: embedded report in a later phase

## Repository structure

```text
frontend/   Next.js UI for Azure Static Web Apps
backend/    Azure Functions Python v2 app
database/   Azure SQL schema and sample data
docs/       Power BI model notes and deployment guidance
```

## Azure settings

Configure these in your Function App environment variables:

```text
AZURE_SQL_SERVER=sql-insightflow-dev-east2.database.windows.net
AZURE_SQL_DATABASE=sqldb-insightflow
FOUNDRY_PROJECT_ENDPOINT=<your Foundry project endpoint>
FOUNDRY_MODEL=<your model deployment name>
FOUNDRY_AGENT_NAME=insightflow-analyst
```

No SQL password is used. The backend uses the Function App system-assigned managed identity.

## API routes

```text
GET  /api/health
GET  /api/schema
GET  /api/top-products?state=Florida&days=90&top=5
POST /api/chat
```

## Azure Static Web Apps build configuration

```text
App location: frontend
API location: <leave blank>
Output location: out
```

Set the frontend environment variable:

```text
NEXT_PUBLIC_API_BASE_URL=https://<your-function-app>.azurewebsites.net/api
```

## Foundry agent

Run `backend/scripts/bootstrap_agent.py` once after your Foundry project and model deployment are ready. The persisted prompt agent exposes only approved business-analysis function tools. The language model is not given unrestricted SQL execution.

## Development order

1. Run `database/schema.sql` and `database/seed.sql` in Azure SQL.
2. Configure Function App settings and managed identity permissions.
3. Deploy `backend` to Azure Functions.
4. Bootstrap the Foundry agent.
5. Deploy `frontend` to Azure Static Web Apps.
6. Add Power BI embedding after the core chat/query flow is verified.
