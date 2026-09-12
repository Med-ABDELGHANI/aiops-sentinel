# Commandes utilisées — Phase 3 : Agent SQL infra

## Création de l'utilisateur PostgreSQL en lecture seule

Voir `docs/commands/phase-2-socle-donnees.md` (créé pendant la Phase 2, utilisé ici par l'agent).

## Mise en place de l'environnement Python

```bash
cd agents/sql_agent
uv venv --python 3.11
source .venv/bin/activate
uv pip install mistralai psycopg2-binary python-dotenv
```

## Figer les dépendances

```bash
uv pip freeze > requirements.txt
```

## Lancer l'agent

```bash
cd agents/sql_agent
source .venv/bin/activate
python main.py
```

## Points techniques notables

- Le SDK `mistralai` v2.10.0 exporte la classe `Mistral` depuis `mistralai.client.sdk`, pas depuis la racine du paquet (`from mistralai.client.sdk import Mistral`).
- Le routeur d'origine (formation) ne permettait qu'un seul tour d'appel d'outils. Passage à une boucle (`max_tool_iterations`) pour permettre l'enchaînement `get_pg_schema` puis `execute_sql_query` dans une même question, avec `tool_choice="auto"` pour laisser le modèle arrêter la boucle de lui-même.
- Tier gratuit Mistral trop limité en débit pour développer sereinement (erreurs 429 répétées) — passage en Pay-As-You-Go.
