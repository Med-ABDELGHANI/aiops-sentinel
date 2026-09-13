# Phase 5 — Orchestration multi-agents (MCP)

## 1. Comprendre cette phase

### Besoin

Les Phases 3 et 4 ont produit deux agents independants : l'un interroge
l'inventaire structure (PostgreSQL), l'autre recherche dans la
documentation technique (Qdrant). Un utilisateur devait jusqu'ici savoir
lui-meme lequel lancer selon sa question. Cette phase construit une
couche d'orchestration unique : un point d'entree conversationnel qui
recoit n'importe quelle question, determine quel(s) agent(s) solliciter,
et renvoie une reponse consolidee.

### Principe general : MCP (Model Context Protocol)

MCP est un protocole standardise qui expose des outils sous une forme
uniforme, consommable par n'importe quel client compatible, plutot qu'un
systeme de function calling propre a chaque application. Concretement,
un serveur MCP declare ses outils via un decorateur (`@mcp.tool`) applique
a des fonctions Python classiques ; le framework (FastMCP) genere
automatiquement leur description (nom, parametres, types) a partir de la
signature de la fonction et de sa docstring, sans qu'il soit necessaire
d'ecrire manuellement un schema JSON comme dans le mecanisme de function
calling construit en Phase 3.

### Architecture

```text
Utilisateur
  -> Orchestrateur (routeur IA, port local)
       -> Serveur MCP sql_server  (port 8001) : get_pg_schema, execute_sql_query, check_server_reachability
       -> Serveur MCP rag_server  (port 8002) : search_ansible_docs
  -> Reponse consolidee
```

Chaque serveur est un processus independant, exposant ses outils via
HTTP. L'orchestrateur se connecte aux serveurs pertinents selon la
question posee, sans jamais dupliquer leur logique metier.

### Les fichiers de cette phase et leur role

**`mcp_servers/sql_server/main.py`**
Reexpose les trois outils de l'agent SQL (Phase 3) sous forme de serveur
MCP. Chaque fonction est identique dans sa logique interne ; seule
l'exposition change, via le decorateur `@mcp.tool`. Le serveur ecoute sur
le port 8001.

**`mcp_servers/rag_server/main.py`**
Expose un unique outil, `search_ansible_docs`, qui effectue la recherche
semantique dans Qdrant et renvoie les passages trouves. Contrairement a
l'agent RAG complet de la Phase 4, ce serveur ne genere pas lui-meme de
reponse : cette responsabilite est deleguee a l'orchestrateur, afin que
le serveur reste focalise sur une seule tache (recuperer de la donnee).
Ecoute sur le port 8002.

**`mcp_servers/orchestrator/main.py`** — fonctions principales

`route_question(question)` : interroge le modele de langage avec une
description des deux agents disponibles, et recupere une decision
strictement structuree en JSON indiquant lequel ou lesquels solliciter.
Le choix est fait par le modele, pas par des regles ecrites a la main,
afin de rester robuste face a des formulations variees en langage
naturel.

`call_sql_agent(question)` : se connecte au serveur MCP sql_server,
recupere dynamiquement la liste de ses outils, et mene une boucle de
function calling classique (identique dans son principe a celle de la
Phase 3) jusqu'a ce que le modele dispose de suffisamment d'informations
pour repondre. Le prompt impose de toujours verifier les valeurs reelles
stockees (via une requete d'echantillon) avant de filtrer sur un critere,
pour eviter toute hypothese erronee sur la langue ou l'orthographe d'une
valeur.

`call_rag_agent(question)` : appelle l'outil `search_ansible_docs` du
serveur rag_server, puis construit un prompt enrichi avec les passages
trouves et genere une reponse via Mistral, en reprenant le meme principe
que l'agent RAG de la Phase 4.

`answer_question(question)` : orchestre l'ensemble. Appelle `route_question`,
puis les agents necessaires, et combine leurs reponses sous des sections
distinctes si les deux ont ete sollicites.

### Relation avec les agents des Phases 3 et 4

Les serveurs MCP ne remplacent pas les agents originaux (`agents/sql_agent/`,
`agents/rag_agent/`), qui restent utilisables independamment. Cette phase
ajoute une couche superieure, capable de solliciter l'un, l'autre, ou les
deux selon le besoin reel de chaque question.

## 2. Commandes utilisees

### Mise en place du serveur SQL

```bash
cd mcp_servers/sql_server
uv venv --python 3.11
source .venv/bin/activate
uv pip install fastmcp psycopg2-binary python-dotenv
python main.py
```

### Mise en place du serveur RAG

```bash
cd mcp_servers/rag_server
uv venv --python 3.11
source .venv/bin/activate
uv pip install fastmcp qdrant-client sentence-transformers python-dotenv
python main.py
```

### Mise en place de l'orchestrateur

```bash
cd mcp_servers/orchestrator
uv venv --python 3.11
source .venv/bin/activate
uv pip install fastmcp mistralai python-dotenv
python main.py
```

### Verification d'un serveur MCP (liste des outils exposes)

```python
import asyncio
from fastmcp import Client

async def main():
    async with Client("http://localhost:8001/mcp") as client:
        tools = await client.list_tools()
        for tool in tools:
            print(f"- {tool.name}: {tool.description}")

asyncio.run(main())
```

### Figer les dependances

```bash
cd mcp_servers/sql_server && uv pip freeze > requirements.txt
cd ../rag_server && uv pip freeze > requirements.txt
cd ../orchestrator && uv pip freeze > requirements.txt
```
