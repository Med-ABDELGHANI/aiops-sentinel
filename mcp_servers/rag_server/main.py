#!/usr/bin/env python3

import os

from dotenv import load_dotenv
from fastmcp import FastMCP
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

load_dotenv()

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "ansible_docs")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

TOP_K = 3

embedding_model = SentenceTransformer(EMBEDDING_MODEL)
qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

mcp = FastMCP("RAG Documentation Server")


@mcp.tool
def search_ansible_docs(query: str, top_k: int = TOP_K) -> list[dict]:
    """Search the Ansible documentation for passages relevant to the query.

    Returns a list of matching passages, each with its text, source URL,
    title, and similarity score.
    """
    query_vector = embedding_model.encode(query).tolist()

    results = qdrant_client.query_points(
        collection_name=QDRANT_COLLECTION,
        query=query_vector,
        limit=top_k,
    )

    return [
        {
            "text": r.payload["text"],
            "url": r.payload["url"],
            "title": r.payload["title"],
            "score": r.score,
        }
        for r in results.points
    ]


if __name__ == "__main__":
    mcp.run(
        host="0.0.0.0",
        port=8002,
        transport="http",
        path="/mcp",
    )
