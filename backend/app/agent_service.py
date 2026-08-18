import os
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient


def _project_client() -> AIProjectClient:
    return AIProjectClient(
        endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        credential=DefaultAzureCredential(),
    )


def ask_agent(question: str) -> str:
    """Send a question to the persisted Foundry prompt agent.

    The agent is created once by scripts/bootstrap_agent.py. This function
    uses the Foundry 2.x project client and the OpenAI Responses API bound
    to the named agent.
    """
    project = _project_client()
    openai = project.get_openai_client(agent_name=os.environ["FOUNDRY_AGENT_NAME"])
    conversation = openai.conversations.create()
    response = openai.responses.create(
        conversation=conversation.id,
        input=question,
    )
    return response.output_text
