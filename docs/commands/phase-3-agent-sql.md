# Phase 3 — Agent SQL infra

## Objectif

Fournir une reponse en langage naturel a des questions portant sur
l'inventaire d'infrastructure (serveurs, services, incidents), via un
mecanisme de function calling : l'agent decouvre le schema reel de la
base, genere des requetes SQL en lecture seule, et verifie la
disponibilite reseau des services concernes.

## Architecture

```text
db/schema.sql + db/seed.sql -> PostgreSQL (une fois)
agents/sql_agent/main.py -> connexion directe a PostgreSQL a chaque question
```

Contrairement a l'agent RAG (Phase 4), il n'y a pas d'etape de preparation
intermediaire regeneree periodiquement : l'agent interroge PostgreSQL en
temps reel, les donnees sont donc toujours a jour.

Trois outils sont exposes au modele de langage :

- `get_pg_schema` : decouverte du schema reel (bases, tables, colonnes)
- `execute_sql_query` : execution d'une requete SELECT, via un utilisateur
  PostgreSQL en lecture seule
- `check_server_reachability` : test de connexion TCP vers un hote/port

Le routeur applique une boucle d'appels d'outils (jusqu'a 5 iterations),
permettant d'enchainer plusieurs outils au sein d'une meme question (par
exemple, decouverte du schema puis execution de la requete).

## Prerequis

- PostgreSQL et Qdrant operationnels (voir Phase 2)
- Utilisateur PostgreSQL en lecture seule `infra_readonly` cree (voir Phase 2)
- Cle API Mistral valide, compte en Pay-As-You-Go

## Procedure

### 1. Mise en place de l'environnement Python

```bash
cd agents/sql_agent
uv venv --python 3.11
source .venv/bin/activate
uv pip install mistralai psycopg2-binary python-dotenv
```

### 2. Figer les dependances

```bash
uv pip freeze > requirements.txt
```

### 3. Lancement

```bash
cd agents/sql_agent
source .venv/bin/activate
python main.py
```

## Configuration

Fichier `.env` (non versionne), a partir de `.env.example` :

```bash
MISTRAL_API_KEY=<cle API Mistral>

PG_HOST=localhost
PG_PORT=5432
PG_DB=aiops_sentinel

PG_ADMIN_USER=aiops
PG_ADMIN_PASSWORD=<mot de passe genere>

PG_READONLY_USER=infra_readonly
PG_READONLY_PASSWORD=<mot de passe genere>
```

## Verification

Interroger l'agent avec une question necessitant une decouverte de schema
suivie d'une requete reelle, par exemple : "Combien d'incidents sont
actuellement ouverts ?". Une reponse valide affiche la requete SQL
utilisee et le resultat chiffre correspondant.

## Depannage

**`ImportError: cannot import name 'Mistral' from 'mistralai'`**

Cause : dans `mistralai==2.10.0`, la classe `Mistral` n'est pas exportee
a la racine du paquet.

Correction :

```python
from mistralai.client.sdk import Mistral
```

**`SDKError: API error occurred: Status 429 (Rate limit exceeded)`**

Cause : quota du tier gratuit Mistral insuffisant pour un usage de
developpement (deux appels API minimum par question).

Correction : activer la facturation a l'usage (Pay-As-You-Go) sur le
compte Mistral.

**L'agent affiche le SQL genere mais jamais le resultat de la requete**

Cause : le prompt systeme, herite de la formation d'origine, demandait
explicitement de n'afficher que la requete SQL, sans le resultat.

Correction : reformuler la consigne pour exiger l'affichage conjoint de
la requete et du resultat en langage naturel.

**L'agent s'arrete apres la decouverte du schema sans executer la requete**

Cause : le mecanisme d'appel d'outils d'origine ne permettait qu'un seul
tour d'appel par question, insuffisant pour enchainer decouverte du
schema puis execution de requete.

Correction : remplacer l'appel unique par une boucle (`max_tool_iterations`),
avec `tool_choice="auto"` pour laisser le modele mettre fin a la boucle
de lui-meme des qu'aucun outil supplementaire n'est necessaire.
