#!/usr/bin/env python3

import asyncio
import json
import os

from dotenv import load_dotenv
from fastmcp import Client
from mistralai.client.sdk import Mistral
from splunk_logger import send_to_splunk  # fonction d'observabilite : envoie des evenements vers Splunk (HEC)

load_dotenv()

api_key_mistral = os.getenv("MISTRAL_API_KEY")
client = Mistral(api_key=api_key_mistral)
model = "mistral-small-2506"
temperature = 0

SQL_SERVER_URL = os.getenv("SQL_SERVER_URL", "http://localhost:8001/mcp")
RAG_SERVER_URL = os.getenv("RAG_SERVER_URL", "http://localhost:8002/mcp")

router_system_prompt = """
You are a router that decides which specialized agent(s) should handle a
user's question about an infrastructure platform.

Available agents:
- sql_agent: queries a structured inventory (servers, services, incidents)
  stored in PostgreSQL. Use for questions about counts, status, existence
  of servers/services/incidents, or network reachability checks.
- rag_agent: searches Ansible technical documentation. Use for questions
  about how Ansible concepts work (playbooks, modules, variables, roles).

Respond ONLY with a single valid JSON object, with exactly these keys:
"agents" (array containing "sql_agent" and/or "rag_agent"), and "reason"
(a short string).

Example: {"agents": ["sql_agent"], "reason": "question about server count"}
"""


def route_question(question: str) -> list[str]:
    """Ask the LLM which agent(s) should handle this question."""
    decision_call = client.chat.complete(
        model=model,
        temperature=0.0,
        messages=[
            {"role": "system", "content": router_system_prompt},
            {"role": "user", "content": f"Question: {question}\n\nRespond only with the JSON object."},
        ],
    )

    decision_text = decision_call.choices[0].message.content.strip()
    print("DEBUG: routing decision:\n" + decision_text)

    try:
        decision_json = json.loads(decision_text)
        agents = decision_json.get("agents", [])
    except json.JSONDecodeError:
        print("Warning: could not parse routing JSON; defaulting to no agent.")
        agents = []

    # Log Splunk : trace la decision de routage (quels agents, pourquoi)
    send_to_splunk("router_decision", {
        "question": question,
        "agents": agents,
    })

    return agents


async def call_sql_agent(question: str) -> str:
    """Call the SQL MCP server's tools relevant to the question, via a
    Mistral function-calling loop against the tools it exposes."""
    async with Client(SQL_SERVER_URL) as mcp_client:
        mcp_tools = await mcp_client.list_tools()

        tools = [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description or "",
                    "parameters": t.input_schema,
                },
            }
            for t in mcp_tools
        ]

        messages = [
            {"role": "system", "content": (
                "You are an infrastructure data assistant. Before generating any "
                "filtered SQL query (e.g. WHERE status = ...), you MUST first "
                "run a sample query (e.g. SELECT DISTINCT status FROM <table>) "
                "to discover the actual stored values. Never guess the language "
                "or spelling of a value (the user's question may be in French "
                "while stored values are in English, or vice versa). Only "
                "generate SELECT queries."
            )},
            {"role": "user", "content": question},
        ]

        for _ in range(5):
            response = client.chat.complete(
                model=model,
                temperature=0.1,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                parallel_tool_calls=False,
            )

            message = response.choices[0].message
            tool_calls = getattr(message, "tool_calls", None)

            if not tool_calls:
                return message.content

            messages.append(message)
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                function_params = json.loads(tool_call.function.arguments)

                print("\nfunction_name: ", function_name, "\nfunction_params: ", function_params)

                result = await mcp_client.call_tool(function_name, function_params)
                result_text = result.content[0].text if result.content else ""

                print("function_result: ", result_text[:500])

                # Log Splunk : trace chaque outil MCP reellement appele et son resultat
                send_to_splunk("tool_call", {
                    "function_name": function_name,
                    "function_params": function_params,
                    "result_preview": result_text[:300],
                })

                messages.append({
                    "role": "tool",
                    "name": function_name,
                    "content": result_text,
                    "tool_call_id": tool_call.id,
                })

        return "L'agent SQL n'a pas pu conclure dans le nombre d'itérations imparti."


async def call_rag_agent(question: str) -> str:
    """Call the RAG MCP server's search tool, then generate an answer
    grounded in the retrieved passages."""
    async with Client(RAG_SERVER_URL) as mcp_client:
        result = await mcp_client.call_tool("search_ansible_docs", {"query": question})
        chunks = json.loads(result.content[0].text) if result.content else []

    if not chunks:
        return "Je n'ai trouvé aucun document pertinent pour répondre à cette question."

    context = "\n\n---\n\n".join(
        f"[Source: {c['title']} - {c['url']}]\n{c['text']}" for c in chunks
    )

    prompt = (
        f"Context extracts:\n\n{context}\n\n"
        f"Question: {question}\n\n"
        "Answer based only on the extracts above. Mention the source URL(s) at the end."
    )

    response = client.chat.complete(
        model=model,
        temperature=temperature,
        messages=[
            {"role": "system", "content": "You are a documentation assistant for Ansible."},
            {"role": "user", "content": prompt},
        ],
    )

    return response.choices[0].message.content


async def answer_question(question: str) -> str:
    agents = route_question(question)

    if not agents:
        return "Je ne sais pas quel agent solliciter pour cette question."

    responses = []

    if "sql_agent" in agents:
        responses.append(("Inventaire infrastructure", await call_sql_agent(question)))

    if "rag_agent" in agents:
        responses.append(("Documentation Ansible", await call_rag_agent(question)))

    if len(responses) == 1:
        final_answer = responses[0][1]
    else:
        final_answer = "\n\n".join(f"### {label}\n{content}" for label, content in responses)

    # Log Splunk : trace la reponse finale consolidee donnee a l'utilisateur
    send_to_splunk("final_answer", {
        "question": question,
        "agents_used": agents,
        "answer": final_answer,
    })

    return final_answer


async def main():
    print("Orchestrateur AIOps Sentinel, pose ta question.")
    print("")

    while True:
        user_input = input("User q/quit $> ")
        if user_input.lower() in ["q", "quit"]:
            print("Good Bye !!")
            break
        answer = await answer_question(user_input)
        print(answer)


if __name__ == "__main__":
    asyncio.run(main())
