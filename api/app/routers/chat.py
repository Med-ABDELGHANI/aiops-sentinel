import json
import os

from dotenv import load_dotenv
from fastapi import APIRouter
from fastmcp import Client
from mistralai.client.sdk import Mistral

from app import schemas

load_dotenv()

api_key_mistral = os.getenv("MISTRAL_API_KEY")
mistral_client = Mistral(api_key=api_key_mistral)
model = "mistral-small-2506"

SQL_SERVER_URL = os.getenv("SQL_SERVER_URL", "http://localhost:8001/mcp")
RAG_SERVER_URL = os.getenv("RAG_SERVER_URL", "http://localhost:8002/mcp")

router = APIRouter(prefix="/chat", tags=["chat"])

router_system_prompt = """
You are a router that decides which specialized agent(s) should handle a
user's question about an infrastructure platform.

Available agents:
- sql_agent: queries a structured inventory (servers, services, incidents).
- rag_agent: searches Ansible technical documentation.

Respond ONLY with a JSON object: {"agents": [...], "reason": "..."}
"""


def route_question(question: str) -> list[str]:
    response = mistral_client.chat.complete(
        model=model,
        temperature=0.0,
        messages=[
            {"role": "system", "content": router_system_prompt},
            {"role": "user", "content": question},
        ],
    )
    try:
        return json.loads(response.choices[0].message.content.strip()).get("agents", [])
    except json.JSONDecodeError:
        return []


async def call_sql_agent(question: str) -> str:
    async with Client(SQL_SERVER_URL) as mcp_client:
        mcp_tools = await mcp_client.list_tools()
        tools = [
            {"type": "function", "function": {
                "name": t.name, "description": t.description or "", "parameters": t.input_schema}}
            for t in mcp_tools
        ]

        messages = [
            {"role": "system", "content": (
                "You are an infrastructure data assistant. Before generating any "
                "filtered SQL query, ALWAYS run a sample query to discover the "
                "actual stored values first. Only generate SELECT queries."
            )},
            {"role": "user", "content": question},
        ]

        for _ in range(5):
            response = mistral_client.chat.complete(
                model=model, temperature=0.1, messages=messages,
                tools=tools, tool_choice="auto", parallel_tool_calls=False,
            )
            message = response.choices[0].message
            tool_calls = getattr(message, "tool_calls", None)

            if not tool_calls:
                return message.content

            messages.append(message)
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                function_params = json.loads(tool_call.function.arguments)
                print("\nfunction_name:", function_name, "\nfunction_params:", function_params)
                result = await mcp_client.call_tool(function_name, function_params)
                result_text = result.content[0].text if result.content else ""
                print("function_result:", result_text[:300])
                messages.append({
                    "role": "tool", "name": function_name,
                    "content": result_text, "tool_call_id": tool_call.id,
                })

        return "L'agent SQL n'a pas pu conclure dans le nombre d'itérations imparti."


async def call_rag_agent(question: str) -> str:
    async with Client(RAG_SERVER_URL) as mcp_client:
        result = await mcp_client.call_tool("search_ansible_docs", {"query": question})
        chunks = json.loads(result.content[0].text) if result.content else []

    if not chunks:
        return "Je n'ai trouvé aucun document pertinent pour répondre à cette question."

    context = "\n\n---\n\n".join(
        f"[Source: {c['title']} - {c['url']}]\n{c['text']}" for c in chunks
    )
    prompt = (
        f"Context extracts:\n\n{context}\n\nQuestion: {question}\n\n"
        "Answer based only on the extracts above. Mention the source URL(s) at the end."
    )

    response = mistral_client.chat.complete(
        model=model, temperature=0,
        messages=[
            {"role": "system", "content": "You are a documentation assistant for Ansible."},
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content


@router.post("/", response_model=schemas.ChatResponse)
async def chat(request: schemas.ChatRequest):
    agents = route_question(request.question)

    if not agents:
        return schemas.ChatResponse(answer="Je ne sais pas quel agent solliciter pour cette question.")

    responses = []
    if "sql_agent" in agents:
        responses.append(("Inventaire infrastructure", await call_sql_agent(request.question)))
    if "rag_agent" in agents:
        responses.append(("Documentation Ansible", await call_rag_agent(request.question)))

    if len(responses) == 1:
        return schemas.ChatResponse(answer=responses[0][1])

    combined = "\n\n".join(f"### {label}\n{content}" for label, content in responses)
    return schemas.ChatResponse(answer=combined)
