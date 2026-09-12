# Commandes utilisées — Phase 4 : Agent RAG documentation

## Flux de données du RAG

crawl_ansible_docs.py -> data/raw/ansible_docs.json -> index_ansible_docs.py -> Qdrant (collection ansible_docs) -> agents/rag_agent/main.py lit Qdrant

Chaque étape est indépendante, reliée par un support persistant (fichier JSON,
puis collection Qdrant) plutôt que par un appel de fonction direct entre
scripts. Le crawl et l'indexation sont exécutés une fois (ou périodiquement) ;
l'agent RAG interroge ensuite Qdrant à chaque question, sans jamais
retoucher au crawl ou à l'indexation.

## Comparaison avec l'Agent SQL (Phase 3)

L'Agent SQL n'a pas d'étape de préparation intermédiaire : il se connecte
directement à PostgreSQL à chaque question (données toujours à jour).
L'Agent RAG, lui, ne voit que ce qui a été indexé dans Qdrant au moment de
la dernière exécution de `index_ansible_docs.py` (données figées jusqu'à
la prochaine réindexation).

## Collecte avec Crawl4AI (dans la VM)

```bash
cd ~/crawler-app
source .venv/bin/activate
python crawl_ansible_docs.py
```

## Autoriser la VM à atteindre Qdrant (pare-feu, sur le PC hôte)

Voir `docs/commands/phase-2-socle-donnees.md`, section firewalld.

## Indexation dans Qdrant (dans la VM)

```bash
uv pip install sentence-transformers qdrant-client
python index_ansible_docs.py
```

## Récupération des scripts et données vers le repo (sur le PC)

```bash
cd ~/aiops-sentinel/crawler
scp aiops-crawler:~/crawler-app/crawl_ansible_docs.py .
scp aiops-crawler:~/crawler-app/index_ansible_docs.py .
scp aiops-crawler:~/crawler-app/ansible_docs.json .
mv ansible_docs.json ../data/raw/ansible_docs.json
```

## Mise en place de l'agent RAG (sur le PC)

```bash
cd agents/rag_agent
uv venv --python 3.11
source .venv/bin/activate
uv pip install mistralai qdrant-client sentence-transformers python-dotenv
```

## Lancer l'agent RAG

```bash
cd agents/rag_agent
source .venv/bin/activate
python main.py
```
