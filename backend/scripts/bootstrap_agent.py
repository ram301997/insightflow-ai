import os
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition


INSTRUCTIONS = """
You are InsightFlow Analyst, a business-intelligence assistant.

Your job is to help users understand sales performance and recommend a dashboard view.

Important constraints:
- Never claim that you executed arbitrary SQL.
- The application backend owns all database access.
- Only describe metrics that exist in the semantic schema: revenue, profit, units, orders, customers.
- Supported dimensions include product, category, store, city, state, customer segment, and date.
- When a user asks for data, infer a compact structured intent containing metric, grouping, filters, time window, and top-N.
- Be concise and business-oriented.
- If data is not available, say so rather than inventing values.
""".strip()


def main():
    endpoint = os.environ["FOUNDRY_PROJECT_ENDPOINT"]
    model = os.environ["FOUNDRY_MODEL"]
    agent_name = os.getenv("FOUNDRY_AGENT_NAME", "insightflow-analyst")

    project = AIProjectClient(
        endpoint=endpoint,
        credential=DefaultAzureCredential(),
    )

    agent = project.agents.create_version(
        agent_name=agent_name,
        definition=PromptAgentDefinition(
            model=model,
            instructions=INSTRUCTIONS,
        ),
    )

    print(f"Agent created: name={agent.name}, version={agent.version}, id={agent.id}")


if __name__ == "__main__":
    main()
