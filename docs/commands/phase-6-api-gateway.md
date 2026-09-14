# Phase 6 — API Gateway (FastAPI)

## 1. Comprendre cette phase

### Besoin

Les Phases 3, 4 et 5 ont produit des agents et un orchestrateur utilisables
uniquement en ligne de commande. Cette phase expose ces capacites via une
vraie API HTTP, accessible par n'importe quel client (navigateur, autre
application, outil de test), avec une documentation interactive generee
automatiquement (Swagger). L'API combine deux natures de service : un CRUD
classique sur l'inventaire structure, et un endpoint conversationnel
s'appuyant sur l'IA.

### Architecture des fichiers

```text
api/
|-- app/
|   |-- main.py              (point d'entree FastAPI)
|   |-- database.py          (connexion SQLAlchemy)
|   |-- models.py            (modeles SQLAlchemy : Server, Service, Incident)
|   |-- schemas.py           (schemas Pydantic pour validation/serialisation)
|   |-- routers/
|       |-- servers.py       (CRUD serveurs)
|       |-- services.py      (CRUD services)
|       |-- incidents.py     (CRUD incidents)
|       |-- chat.py          (endpoint chat -> orchestrateur)
|-- requirements.txt
```

### Les fichiers et leur role

**`app/database.py`**
Configure la connexion SQLAlchemy a PostgreSQL (moteur, fabrique de
sessions), et expose `get_db()`, une dependency FastAPI qui fournit une
session fraiche a chaque requete et la ferme automatiquement une fois la
reponse envoyee.

**`app/models.py`**
Definit les modeles SQLAlchemy `Server`, `Service`, `Incident`, miroir
Python de la structure definie en SQL brut dans `db/schema.sql`. Ces deux
representations coexistent : le SQL brut reste utilise par les agents
(Phases 3 et 5), les modeles SQLAlchemy servent uniquement a l'API.

**`app/schemas.py`**
Definit les schemas Pydantic utilises pour valider les donnees recues
(`XxxCreate`, `XxxUpdate`) et structurer les donnees renvoyees (`XxxOut`),
independamment de la structure de stockage. Inclut egalement `ChatRequest`
et `ChatResponse` pour l'endpoint conversationnel.

**`app/routers/servers.py`, `services.py`, `incidents.py`**
Implementent un CRUD complet (creation, lecture, modification partielle,
suppression) pour chaque table de l'inventaire, en utilisant les modeles
et schemas definis plus haut, avec injection de session via `Depends(get_db)`.

**`app/routers/chat.py`**
Reexpose la logique de l'orchestrateur (Phase 5) sous forme d'un endpoint
HTTP unique (`POST /chat/`). Le routage vers l'agent SQL et/ou l'agent RAG,
ainsi que la communication avec les serveurs MCP correspondants, reprend
la meme logique que l'orchestrateur en ligne de commande, adaptee a un
appel HTTP unique plutot qu'a une boucle interactive.

**`app/main.py`**
Assemble l'application FastAPI et y attache chaque routeur. Point d'entree
utilise par Uvicorn pour demarrer le serveur.

### Relation avec les phases precedentes

L'API ne redefinit aucune logique metier nouvelle : le CRUD s'appuie sur
la meme structure de donnees que la Phase 2, et l'endpoint chat reutilise
integralement l'architecture MCP de la Phase 5 (serveurs SQL et RAG,
routeur IA). Cette phase ajoute uniquement une couche d'acces HTTP
au-dessus de l'existant.

## 2. Commandes utilisees

### Mise en place de l'environnement

```bash
cd api
uv venv --python 3.11
source .venv/bin/activate
uv pip install fastapi uvicorn sqlalchemy psycopg2-binary python-dotenv fastmcp mistralai pydantic
uv pip freeze > requirements.txt
```

### Prerequis au lancement

Le CRUD necessite PostgreSQL actif. L'endpoint `/chat` necessite en plus
les deux serveurs MCP actifs (Phase 5, ports 8001 et 8002).

### Lancement du serveur

```bash
cd api
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Acces a la documentation interactive

```text
http://localhost:8000/docs
```

### Test rapide en ligne de commande

```bash
curl -X POST http://localhost:8000/chat/ \
  -H "Content-Type: application/json" \
  -d '{"question": "Combien de serveurs sont actifs ?"}'
```
