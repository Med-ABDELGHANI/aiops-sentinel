#!/usr/bin/env python3

import json
import os
import socket
import time

import psycopg2
from mistralai.client.sdk import Mistral
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor
from splunk_logger import send_to_splunk  # fonction d'observabilite : envoie des evenements vers Splunk (HEC)

load_dotenv()

api_key_mistral = os.getenv("MISTRAL_API_KEY")
client = Mistral(api_key=api_key_mistral)
model = "mistral-small-2506"
temperature = 0

PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_DB = os.getenv("PG_DB", "aiops_sentinel")
PG_ADMIN_USER = os.getenv("PG_ADMIN_USER", "aiops")
PG_ADMIN_PASSWORD = os.getenv("PG_ADMIN_PASSWORD", "")
PG_READONLY_USER = os.getenv("PG_READONLY_USER", "infra_readonly")
PG_READONLY_PASSWORD = os.getenv("PG_READONLY_PASSWORD", "")

system_prompt = """
You are an infrastructure operations assistant with access to tools for
PostgreSQL schema discovery, read-only SQL query execution, and server
reachability checks against an infrastructure inventory (servers, services,
incidents).

Behavior rules (MUST follow):
1. For any user request about servers, services, incidents, tables, columns,
   SQL, or queries you MUST first call the get_pg_schema tool and include its
   result in the conversation before generating or returning any SQL or
   schema-specific answer.
2. Do NOT fabricate table or column names; only use names present in the
   get_pg_schema result.
3. If get_pg_schema returns an error or incomplete data, ask the user for
   connection details or explicitly request permission to proceed.
4. Keep SQL concise, valid for PostgreSQL, and strictly constrained to the
   returned schema.
5. Only generate SELECT queries. Never generate INSERT, UPDATE, DELETE, DROP,
   ALTER or any other write/DDL statement.
6. When the user asks a question that requires real data (not just
   structure), call execute_sql_query with a valid SELECT query after having
   called get_pg_schema.
7. When the user asks whether a specific server or service is reachable,
   call check_server_reachability with the relevant host and port.
8. If the user request is not about the database schema, SQL, or server
   reachability, do not call any tool.

When presenting SQL results, ALWAYS show both:
1. The SQL query used, formatted as a markdown code block:
```sql
SELECT * FROM servers;
```
2. The actual result, summarized clearly in natural language right after the query.
"""


## Functions

def check_server_reachability(host: str, port: int, timeout: float = 3.0) -> str:
    """Check whether a TCP port on a given host is reachable.

    Args:
        host (str): hostname or IP address to test
        port (int): TCP port to test
        timeout (float, optional): connection timeout in seconds. Defaults to 3.0.

    Returns:
        string: reachability result
    """
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return f"{host}:{port} is reachable."
    except (socket.timeout, ConnectionRefusedError, OSError) as e:
        return f"{host}:{port} is NOT reachable ({str(e)})."


def get_pg_schema(host=PG_HOST, port=PG_PORT, user=PG_ADMIN_USER, password=PG_ADMIN_PASSWORD) -> dict:
    """Get PostgreSQL schema for all databases

    Args:
        host (str, optional): host to connect to postgres.
        port (int, optional): port used by postgres.
        user (str, optional): postgres user.
        password (str, optional): user password.

    Returns:
        dict: a descriptive database schema
    """
    conn = psycopg2.connect(host=host, port=port, user=user, password=password, dbname="postgres")
    result = {}
    conn.autocommit = True

    with conn.cursor() as cur:
        cur.execute("""
                      SELECT datname
                      FROM pg_database
                      WHERE datistemplate = false;
                    """)
        databases = [row[0] for row in cur.fetchall()]

    conn.close()

    for db in databases:
        result[db] = {}

        conn = psycopg2.connect(host=host, port=port, user=user, password=password, dbname=db)

        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                          SELECT table_schema, table_name, column_name
                          FROM information_schema.columns
                          WHERE table_schema NOT LIKE 'pg_%'
                          AND table_schema <> 'information_schema'
                          ORDER BY table_schema, table_name, ordinal_position;
                        """)
            rows = cur.fetchall()

            for r in rows:
                schema = r["table_schema"]
                table = r["table_name"]
                column = r["column_name"]

                result[db].setdefault(schema, {})
                result[db][schema].setdefault(table, [])
                result[db][schema][table].append(column)

        conn.close()

    return result


def execute_sql_query(query: str, host=PG_HOST, port=PG_PORT, user=PG_READONLY_USER,
                       password=PG_READONLY_PASSWORD, dbname=PG_DB) -> str:
    """Execute a read-only SQL SELECT query against the infrastructure database.

    Args:
        query (str): a valid PostgreSQL SELECT query
        host (str, optional): PostgreSQL host.
        port (int, optional): PostgreSQL port.
        user (str, optional): read-only PostgreSQL user.
        password (str, optional): password for the read-only user.
        dbname (str, optional): database name to query.

    Returns:
        string: the query results as JSON text, or an error message
    """
    normalized = query.strip().lower()
    if not normalized.startswith("select"):
        return "Error: only SELECT queries are allowed."

    try:
        conn = psycopg2.connect(host=host, port=port, user=user, password=password, dbname=dbname)
        conn.autocommit = True

        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            rows = cur.fetchall()

        conn.close()

        if not rows:
            return "No results found."

        return json.dumps(rows, default=str)

    except Exception as e:
        return f"Error executing query: {str(e)}"


## Function list

functions = {
    'check_server_reachability': check_server_reachability,
    'get_pg_schema': get_pg_schema,
    'execute_sql_query': execute_sql_query
}

tools = [
    {
        "type": "function",
        "function": {
            "name": "check_server_reachability",
            "description": "Check whether a TCP port on a given host is reachable",
            "parameters": {
                "type": "object",
                "properties": {
                    "host": {"type": "string", "description": "Hostname or IP address"},
                    "port": {"type": "integer", "description": "TCP port to test"}
                },
                "required": ["host", "port"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_pg_schema",
            "description": "Get PostgreSQL database schema for all databases including tables and columns names",
            "parameters": {
                "type": "object",
                "properties": {
                    "host": {"type": "string", "description": "PostgreSQL host"},
                    "port": {"type": "integer", "description": "PostgreSQL port"},
                    "user": {"type": "string", "description": "PostgreSQL user"},
                    "password": {"type": "string", "description": "PostgreSQL password"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_sql_query",
            "description": "Execute a read-only SQL SELECT query on the infrastructure database and return the results",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "A valid PostgreSQL SELECT query, using only tables/columns confirmed by get_pg_schema"
                    }
                },
                "required": ["query"]
            }
        }
    }
]

## Conversation

class Conversation:
    def __init__(self):
        self.model = model
        self.temperature = temperature
        self.client = client
        self.conversation_history = [{"role": "system", "content": system_prompt}]

        tools_desc_lines = []
        for t in tools:
            f = t.get("function", {})
            name = f.get("name", "")
            desc = f.get("description", "")
            tools_desc_lines.append(f"- {name}: {desc}")
        tools_desc = "\n".join(tools_desc_lines) if tools_desc_lines else "(no tools available)"

        self.decision_system = (
            "You are a router that decides whether the user's message requires calling external tools.\n"
            "Available tools:\n"
            f"{tools_desc}\n"
            "INSTRUCTIONS: Respond ONLY with a single valid JSON object and nothing else.\n"
            "The JSON must contain exactly these keys: \"use_tools\" (true/false), \"tools\" (an array of tool names, or []), and \"reason\" (a short string).\n"
            "Example: {\"use_tools\": true, \"tools\": [\"get_pg_schema\"], \"reason\": \"user asked about the database structure\"}"
        )

    def new_message(self, message: str) -> str:
        self.conversation_history.append({"role": "user", "content": message})

        decision_call = self.client.chat.complete(
            model=self.model,
            temperature=0.0,
            messages=[
                {"role": "system", "content": self.decision_system},
                {"role": "user", "content": (
                    f"User message:\n{message}\n\n"
                    "Based only on the content, should a tool be used?\n"
                    "Remember: reply ONLY with the single JSON object as described in the system instruction."
                )}
            ]
        )

        decision_text = decision_call.choices[0].message.content.strip()
        time.sleep(1)

        print("DEBUG: router decision text:\n" + (decision_text or "<empty>"))
        try:
            decision_json = json.loads(decision_text)
        except json.JSONDecodeError:
            print("Warning: could not parse decision JSON; assuming no tools.")
            decision_json = {"use_tools": False, "tools": [], "reason": "parse_error"}

        # Log Splunk : trace la decision du routeur (quels outils, pourquoi)
        send_to_splunk("router_decision", {
            "question": message,
            "use_tools": decision_json.get("use_tools"),
            "tools": decision_json.get("tools", []),
            "reason": decision_json.get("reason", ""),
        })

        if decision_json.get("use_tools") and decision_json.get("tools"):
            recommended_tools = decision_json.get("tools", [])
            filtered_tools = [t for t in tools if t.get("function", {}).get("name") in recommended_tools]

            max_tool_iterations = 5
            for _ in range(max_tool_iterations):
                if not filtered_tools:
                    break

                chat_tools = self.client.chat.complete(
                    model=self.model,
                    temperature=0.1,
                    messages=self.conversation_history,
                    tools=filtered_tools,
                    tool_choice="auto",
                    parallel_tool_calls=False,
                )

                tool_calls = None
                if chat_tools.choices:
                    tool_calls = getattr(chat_tools.choices[0].message, "tool_calls", None)

                if not tool_calls:
                    break

                self.conversation_history.append(chat_tools.choices[0].message)
                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    function_params = json.loads(tool_call.function.arguments)

                    print("\nfunction_name: ", function_name, "\nfunction_params: ", function_params)

                    function_result = functions[function_name](**function_params)

                    if isinstance(function_result, str):
                        result_content = function_result
                    else:
                        result_content = json.dumps(function_result)

                    # Log Splunk : trace chaque outil reellement execute et son resultat
                    send_to_splunk("tool_call", {
                        "function_name": function_name,
                        "function_params": function_params,
                        "result_preview": result_content[:300],
                    })

                    self.conversation_history.append({
                        "role": "tool",
                        "name": function_name,
                        "content": result_content,
                        "tool_call_id": tool_call.id,
                    })

        chat_response = self.client.chat.complete(
            model=self.model,
            temperature=self.temperature,
            messages=self.conversation_history,
        )

        chat_response = chat_response.choices[0].message.content
        self.conversation_history.append({"role": "assistant", "content": chat_response})

        # Log Splunk : trace la reponse finale donnee a l'utilisateur
        send_to_splunk("final_answer", {
            "question": message,
            "answer": chat_response,
        })

        return chat_response

    def get_conversation(self):
        return self.conversation_history

    def clear_conversation(self):
        self.conversation_history = [self.conversation_history[0]]
        return self.conversation_history


def main():
    print("Assistant infra AIOps Sentinel, pose ta question.")
    print("")

    discussion = Conversation()

    while True:
        user_input = input("User q/quit, h/history, c/clear $> ")
        if user_input.lower() in ["q", "quit"]:
            print("Good Bye !!")
            break
        elif user_input in ["h", "history"]:
            print(discussion.get_conversation())
        elif user_input in ["c", "clear"]:
            print(discussion.clear_conversation())
            continue
        else:
            print(discussion.new_message(user_input))


if __name__ == "__main__":
    main()
