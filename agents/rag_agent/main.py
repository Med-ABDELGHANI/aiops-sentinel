#!/usr/bin/env python3

import os

from mistralai.client.sdk import Mistral
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

load_dotenv()

api_key_mistral = os.getenv("MISTRAL_API_KEY")
client = Mistral(api_key=api_key_mistral)
model = "mistral-small-2506"
temperature = 0

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "ansible_docs")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

TOP_K = 3

system_prompt = """
You are a documentation assistant for Ansible. You answer questions ONLY
based on the context extracts provided to you. If the extracts do not
contain enough information to answer, say so clearly instead of guessing
or using outside knowledge.

Always mention which source URL(s) the answer is based on, at the end of
your response.
"""

embedding_model = SentenceTransformer(EMBEDDING_MODEL)
qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)


def search_docs(query: str, top_k: int = TOP_K):
    """Search the Qdrant collection for the most relevant document chunks.

    Args:
        query (str): the user's question
        top_k (int, optional): number of chunks to retrieve. Defaults to TOP_K.

    Returns:
        list: matching chunks with their text, url, title, and score
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

'''
    resultats = []
    for r in results.points:
        resultats.append({
            "text": r.payload["text"],
            "url": r.payload["url"],
            "title": r.payload["title"],
            "score": r.score,
    })
    return resultats
'''


def build_prompt(query: str, chunks: list) -> str:
    """Build the final prompt sent to the LLM, with retrieved context.

    Args:
        query (str): the user's question
        chunks (list): the retrieved chunks from search_docs

    Returns:
        string: the assembled prompt
    """
    context = "\n\n---\n\n".join(
        f"[Source: {c['title']} - {c['url']}]\n{c['text']}" for c in chunks
    )

    return (
        f"Context extracts:\n\n{context}\n\n"
        f"Question: {query}\n\n"
        "Answer based only on the extracts above."
    )


class RagConversation:
    def __init__(self):
        self.model = model
        self.temperature = temperature
        self.client = client
        self.conversation_history = [{"role": "system", "content": system_prompt}]

    def new_message(self, message: str) -> str:
        chunks = search_docs(message)

        if not chunks:
            answer = "Je n'ai trouvé aucun document pertinent pour répondre à cette question."
            self.conversation_history.append({"role": "user", "content": message})
            self.conversation_history.append({"role": "assistant", "content": answer})
            return answer

        enriched_prompt = build_prompt(message, chunks)
        self.conversation_history.append({"role": "user", "content": enriched_prompt})

        chat_response = self.client.chat.complete(
            model=self.model,
            temperature=self.temperature,
            messages=self.conversation_history,
        )

        answer = chat_response.choices[0].message.content
        self.conversation_history.append({"role": "assistant", "content": answer})
        return answer

    def get_conversation(self):
        return self.conversation_history

    def clear_conversation(self):
        self.conversation_history = [self.conversation_history[0]]
        return self.conversation_history


def main():
    print("Assistant documentation Ansible (RAG), pose ta question.")
    print("")

    discussion = RagConversation()

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
