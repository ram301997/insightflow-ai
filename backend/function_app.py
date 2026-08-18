import json
import re
import azure.functions as func

from app.db import get_kpis, get_top_products
from app.schema import SEMANTIC_SCHEMA
from app.dashboard import build_dashboard_action, get_dashboard_metadata
from app.agent_service import ask_agent

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


def _json(data, status=200):
    return func.HttpResponse(
        json.dumps(data, default=str),
        status_code=status,
        mimetype="application/json",
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
        },
    )


def _parse_simple_intent(question: str):
    """Safe MVP parser. It maps natural language to an allowlisted query.

    Foundry is used for the narrative answer, while SQL execution remains
    deterministic and parameterized in app/db.py.
    """
    text = question.lower()
    state_map = {
        "florida": "Florida",
        "texas": "Texas",
        "new york": "New York",
        "california": "California",
        "illinois": "Illinois",
        "georgia": "Georgia",
    }
    state = next((value for key, value in state_map.items() if key in text), None)

    days_match = re.search(r"(?:last|past)\s+(\d+)\s+days", text)
    days = int(days_match.group(1)) if days_match else 90

    top_match = re.search(r"top\s+(\d+)", text)
    top = int(top_match.group(1)) if top_match else 5

    if "product" in text or "products" in text:
        return {"intent": "top_products", "state": state or "Florida", "days": days, "top": top}

    return {"intent": "kpis", "state": state, "days": days}


@app.route(route="health", methods=["GET", "OPTIONS"])
def health(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return _json({"ok": True})
    return _json({"status": "ok", "service": "InsightFlow AI API"})


@app.route(route="schema", methods=["GET"])
def schema(req: func.HttpRequest) -> func.HttpResponse:
    return _json(SEMANTIC_SCHEMA)


@app.route(route="top-products", methods=["GET"])
def top_products(req: func.HttpRequest) -> func.HttpResponse:
    try:
        state = req.params.get("state", "Florida")
        days = int(req.params.get("days", "90"))
        top = int(req.params.get("top", "5"))
        rows = get_top_products(state=state, days=days, top=top)
        return _json({"data": rows, "dashboardAction": build_dashboard_action(page="product", state=state, days=days)})
    except Exception as exc:
        return _json({"error": str(exc)}, 500)


@app.route(route="chat", methods=["POST", "OPTIONS"])
def chat(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return _json({"ok": True})

    try:
        body = req.get_json()
        question = (body.get("question") or "").strip()
        if not question:
            return _json({"error": "question is required"}, 400)

        parsed = _parse_simple_intent(question)

        if parsed["intent"] == "top_products":
            data = get_top_products(parsed["state"], parsed["days"], parsed["top"])
            action = build_dashboard_action(page="product", state=parsed["state"], days=parsed["days"])
        else:
            data = get_kpis(parsed.get("state"), parsed["days"])
            action = build_dashboard_action(page="overview", state=parsed.get("state"), days=parsed["days"])

        prompt = (
            "User question: " + question + "\n\n"
            "Verified database result (do not change or invent numbers):\n" + json.dumps(data, default=str) + "\n\n"
            "Give a concise executive BI answer based only on this verified result."
        )

        try:
            answer = ask_agent(prompt)
        except Exception:
            answer = "I retrieved the requested business data successfully. Review the returned metrics and dashboard update below."

        return _json({
            "answer": answer,
            "data": data,
            "intent": parsed,
            "dashboardAction": action,
            "dashboardMetadata": get_dashboard_metadata(),
        })
    except Exception as exc:
        return _json({"error": str(exc)}, 500)
