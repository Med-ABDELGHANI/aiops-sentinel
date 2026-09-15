import json
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

import os
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
COLLECTION_NAME = "ansible_docs"
CHUNK_SIZE = 800

model = SentenceTransformer("all-MiniLM-L6-v2")
client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, timeout=60)


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE) -> list[str]:
    """Découpe un texte en morceaux de taille fixe, sur les paragraphes."""
    paragraphs = text.split("\n\n")
    chunks = []
    current = ""

    for p in paragraphs:
        if len(current) + len(p) < chunk_size:
            current += p + "\n\n"
        else:
            if current.strip():
                chunks.append(current.strip())
            current = p + "\n\n"

    if current.strip():
        chunks.append(current.strip())

    return chunks


def main():
    # Ce fichier vit dans data/raw/ansible_docs.json (données brutes du projet) ;
    # ce script s'attend à être lancé depuis ce même dossier data/raw/.
    with open("ansible_docs.json") as f:
        documents = json.load(f)

    all_chunks = []
    for doc in documents:
        chunks = chunk_text(doc["markdown"])
        for chunk in chunks:
            all_chunks.append({
                "text": chunk,
                "url": doc["url"],
                "title": doc["title"]
            })

    print(f"{len(all_chunks)} chunks générés à partir de {len(documents)} pages.")

    texts = [c["text"] for c in all_chunks]
    embeddings = model.encode(texts, show_progress_bar=True)
    vector_size = embeddings.shape[1]

    if client.collection_exists(COLLECTION_NAME):
        client.delete_collection(COLLECTION_NAME)

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE)
    )
    
    '''
    points = [
        PointStruct(
            id=i,
            vector=embeddings[i].tolist(),
            payload={
                "text": all_chunks[i]["text"],
                "url": all_chunks[i]["url"],
                "title": all_chunks[i]["title"]
            }
        )
        for i in range(len(all_chunks))
    ]
    '''
    points = []
    for i in range(len(all_chunks)):
        points.append(
            PointStruct(
                id=i,
                vector=embeddings[i].tolist(),
                payload={
                    "text": all_chunks[i]["text"],
                    "url": all_chunks[i]["url"],
                    "title": all_chunks[i]["title"]
            }
        )
    )

    client.upsert(collection_name=COLLECTION_NAME, points=points)
    print(f"{len(points)} chunks indexés dans la collection '{COLLECTION_NAME}'.")


if __name__ == "__main__":
    main()
