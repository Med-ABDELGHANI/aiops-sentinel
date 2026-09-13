#!/usr/bin/env python3

import json
import os
import socket

import psycopg2
from dotenv import load_dotenv
from fastmcp import FastMCP
from psycopg2.extras import RealDictCursor

load_dotenv()

PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_DB = os.getenv("PG_DB", "aiops_sentinel")
PG_ADMIN_USER = os.getenv("PG_ADMIN_USER", "aiops")
PG_ADMIN_PASSWORD = os.getenv("PG_ADMIN_PASSWORD", "")
PG_READONLY_USER = os.getenv("PG_READONLY_USER", "infra_readonly")
PG_READONLY_PASSWORD = os.getenv("PG_READONLY_PASSWORD", "")

mcp = FastMCP("SQL Infra Server")


@mcp.tool
def check_server_reachability(host: str, port: int, timeout: float = 3.0) -> str:
    """Check whether a TCP port on a given host is reachable."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return f"{host}:{port} is reachable."
    except (socket.timeout, ConnectionRefusedError, OSError) as e:
        return f"{host}:{port} is NOT reachable ({str(e)})."


@mcp.tool
def get_pg_schema(
    host: str = PG_HOST,
    port: int = PG_PORT,
    user: str = PG_ADMIN_USER,
    password: str = PG_ADMIN_PASSWORD,
) -> dict:
    """Get PostgreSQL schema for all databases (tables and columns)."""
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


@mcp.tool
def execute_sql_query(
    query: str,
    host: str = PG_HOST,
    port: int = PG_PORT,
    user: str = PG_READONLY_USER,
    password: str = PG_READONLY_PASSWORD,
    dbname: str = PG_DB,
) -> str:
    """Execute a read-only SQL SELECT query against the infrastructure database."""
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


if __name__ == "__main__":
    mcp.run(
        host="0.0.0.0",
        port=8001,
        transport="http",
        path="/mcp",
    )
