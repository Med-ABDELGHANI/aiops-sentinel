#!/usr/bin/env python3

"""
Variante non utilisee de l'orchestrateur, conservee a titre de reference
et de comparaison avec l'architecture MCP reelle (main.py).

Contrairement a main.py, cette version n'utilise aucun serveur MCP :
les fonctions outils (SQL, RAG) sont importees et appelees directement
en local, sans communication reseau. La description des outils SQL
(sql_tools) doit donc etre ecrite manuellement, comme dans l'agent SQL
classique (agents/sql_agent/main.py), au lieu d'etre decouverte
automatiquement via list_tools() comme le fait main.py.

Ce fichier n'est pas execute dans le cadre du projet ; il illustre
l'alternative architecturale evoquee en Phase 5.
"""

import json
import os

from mistralai.client.sdk import Mistral
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor
import socket
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

load_dotenv()

api_key_mistral = os.getenv("MISTRAL_API_KEY")
client = Mistral(api_key=api_key_mistral)
model = "mistral-small-2506"

PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_DB = os.getenv("PG_DB", "aiops_sentinel")
PG_ADMIN_USER = os.getenv("PG_ADMIN_USER", "aiops")
PG_ADMIN_PASSWORD = os.getenv("PG_ADMIN_PASSWORD", "")
PG_READONLY_USER = os.getenv("PG_READONLY_USER", "infra_readonly")
PG_READONLY_PASSWORD = os.getenv("PG_READONLY_PASSWORD", "")

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "ansible_docs")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

embedding_model = SentenceTransformer(EMBEDDING_MODEL)
qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)


## --- Fonctions "outils", copiees directement des agents classiques ---

def check_server_reachability(host: str, port: int, timeout: float = 3.0) -> str:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return f"{host}:{port} is reachable."
    except (socket.timeout, ConnectionRefusedError, OSError) as e:
        return f"{host}:{port} is NOT reachable ({str(e)})."


def get_pg_schema(host=PG_HOST, port=PG_PORT, user=PG_ADMIN_USER, password=PG_ADMIN_PASSWORD) -> dict:
    conn = psycopg2.connect(host=host, port=port, user=user, password=password, dbname="postgres")
    result = {}
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("SELECT datname FROM pg_database WHERE datistemplate = false;")
        databases = [row[0] for row in cur.fetchall()]
    conn.close()

    for db in databases:
        result[db] = {}
        conn = psycopg2.connect(host=host, port=port, user=user, password=password, dbname=db)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT table_schema, table_name, column_name
                FROM information_schema.columns
                WHERE table_schema NOT LIKE 'pg_%' AND table_schema <> 'information_schema'
                ORDER BY table_schema, table_name, ordinal_position;
            """)
            for r in cur.fetchall():
                result[db].setdefault(r["table_schema"], {})
                result[db][r["table_schema"]].setdefault(r["table_name"], [])
                result[db][r["table_schema"]][r["table_name"]].append(r["column_name"])
        conn.close()
    return result


def execute_sql_query(query: str, host=PG_HOST, port=PG_PORT, user=PG_READONLY_USER,
                       password=PG_READONLY_PASSWORD, dbname=PG_DB) -> str:
    if not query.strip().lower().startswith("select"):
        return "Error: only SELECT queries are allowed."
    try:
        conn = psycopg2.connect(host=host, port=port, user=user, password=password, dbname=dbname)
        conn.autocommit = True
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            rows = cur.fetchall()
        conn.close()
        return json.dumps(rows, default=str) if rows else "No results found."
    except Exception as e:
        return f"Error executing query: {str(e)}"


def search_ansible_docs(query: str, top_k: int = 3) -> list:
    query_vector = embedding_model.encode(query).tolist()
    results = qdrant_client.query_points(
        collection_name=QDRANT_COLLECTION, query=query_vector, limit=top_k
    )
    return [
        {"text": r.payload["text"], "url": r.payload["url"], "title": r.payload["title"], "score": r.score}
        for r in results.points
    ]


## --- Description des outils SQL (necessaire ici, pas de decouverte automatique) ---

sql_functions = {
    "check_server_reachability": check_server_reachability,
    "get_pg_schema": get_pg_schema,
    "execute_sql_query": execute_sql_query,
}

sql_tools = [
    {"type": "function", "function": {
        "name": "check_server_reachability",
        "description": "Check whether a TCP port on a given host is reachable",
        "parameters": {"type": "object", "properties": {
            "host": {"type": "string"}, "port": {"type": "integer"}}, "required": ["host", "port"]}}},
    {"type": "function", "function": {
        "name": "get_pg_schema",
        "description": "Get PostgreSQL database schema (tables and columns)",
        "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {
        "name": "execute_sql_query",
        "description": "Execute a read-only SQL SELECT query",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string"}}, "required": ["query"]}}},
]


## --- Routeur ---

router_system_prompt = """
You are a router that decides which agent(s) should handle a question.
Available agents:
- sql_agent: infrastructure inventory (servers, services, incidents)
- rag_agent: Ansible documentation
Respond ONLY with JSON: {"agents": [...], "reason": "..."}
"""


def route_question(question: str) -> list:
    response = client.chat.complete(
        model=model, temperature=0.0,
        messages=[
            {"role": "system", "content": router_system_prompt},
            {"role": "user", "content": question},
        ],
    )
    try:
        return json.loads(response.choices[0].message.content.strip()).get("agents", [])
    except json.JSONDecodeError:
        return []


## --- Agent SQL (function calling local, boucle identique a l'Agent SQL classique) ---

def call_sql_agent(question: str) -> str:
    messages = [
        {"role": "system", "content": "You are an infrastructure data assistant. Always verify real stored values before filtering."},
        {"role": "user", "content": question},
    ]

    for _ in range(5):
        response = client.chat.complete(
            model=model, temperature=0.1, messages=messages,
            tools=sql_tools, tool_choice="auto", parallel_tool_calls=False,
        )
        message = response.choices[0].message
        tool_calls = getattr(message, "tool_calls", None)

        if not tool_calls:
            return message.content

        messages.append(message)
        for tool_call in tool_calls:
            function_name = tool_call.function.name
            function_params = json.loads(tool_call.function.arguments)
            result = sql_functions[function_name](**function_params)  # appel LOCAL direct
            messages.append({
                "role": "tool", "name": function_name,
                "content": result if isinstance(result, str) else json.dumps(result),
                "tool_call_id": tool_call.id,
            })

    return "Nombre d'iterations depasse."


## --- Agent RAG (appel local direct, pas de boucle necessaire) ---

def call_rag_agent(question: str) -> str:
    chunks = search_ansible_docs(question)  # appel LOCAL direct
    if not chunks:
        return "Aucun document pertinent trouve."

    context = "\n\n---\n\n".join(f"[Source: {c['title']} - {c['url']}]\n{c['text']}" for c in chunks)
    prompt = f"Context extracts:\n\n{context}\n\nQuestion: {question}\n\nAnswer based only on the extracts above."

    response = client.chat.complete(
        model=model, temperature=0,
        messages=[{"role": "system", "content": "You are a documentation assistant."},
                  {"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


## --- Orchestration ---

def answer_question(question: str) -> str:
    agents = route_question(question)
    if not agents:
        return "Je ne sais pas quel agent solliciter."

    responses = []
    if "sql_agent" in agents:
        responses.append(("Inventaire infrastructure", call_sql_agent(question)))
    if "rag_agent" in agents:
        responses.append(("Documentation Ansible", call_rag_agent(question)))

    if len(responses) == 1:
        return responses[0][1]
    return "\n\n".join(f"### {label}\n{content}" for label, content in responses)


def main():
    print("Orchestrateur (version import direct), pose ta question.")
    while True:
        user_input = input("User q/quit $> ")
        if user_input.lower() in ["q", "quit"]:
            break
        print(answer_question(user_input))


if __name__ == "__main__":
    main()
