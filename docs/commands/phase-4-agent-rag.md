# Phase 4 — Agent RAG documentation

## Objectif

Fournir une reponse en langage naturel a des questions sur la documentation
Ansible, en s'appuyant sur une recherche par similarite semantique plutot
que sur la memoire du modele de langage seul. L'agent retrouve les passages
de documentation les plus pertinents et genere sa reponse a partir de ces
extraits, avec citation systematique des sources.

## Architecture

```text
Collecte (Crawl4AI) -> data/raw/ansible_docs.json
                     -> Indexation (embeddings + Qdrant)
                     -> Agent RAG (recherche + generation)
```

La collecte et l'indexation sont executees une fois (ou a chaque mise a jour
de la documentation source). L'agent interroge ensuite la collection Qdrant
a chaque question, sans dependance directe avec les scripts de collecte.

## Prerequis

- VM Vagrant `aiops-crawler` operationnelle avec Crawl4AI installe (voir Phase 2)
- Conteneur Qdrant actif sur l'hote (port 6333)
- Regle firewalld autorisant le sous-reseau de la VM vers le port 6333 (voir Phase 2)
- Cle API Mistral valide, compte en Pay-As-You-Go

## Procedure

### 1. Collecte de la documentation source

Sur la VM `aiops-crawler` :

```bash
cd ~/crawler-app
source .venv/bin/activate
python crawl_ansible_docs.py
```

Ce script scrape trois pages de la documentation officielle Ansible
(introduction aux playbooks, variables, introduction aux modules) via
Crawl4AI, et produit un fichier `ansible_docs.json` contenant, pour
chaque page, son URL, son titre et son contenu converti en markdown.

### 2. Indexation dans Qdrant

Toujours sur la VM :

```bash
uv pip install sentence-transformers qdrant-client
python index_ansible_docs.py
```

Ce script decoupe le contenu de chaque page en segments d'environ
800 caracteres (sur les frontieres de paragraphes), genere un vecteur
d'embedding pour chaque segment via le modele `all-MiniLM-L6-v2`, et
indexe l'ensemble dans une collection Qdrant nommee `ansible_docs`.

### 3. Recuperation des artefacts vers le depot

Depuis le poste de travail :

```bash
cd ~/aiops-sentinel/crawler
scp aiops-crawler:~/crawler-app/crawl_ansible_docs.py .
scp aiops-crawler:~/crawler-app/index_ansible_docs.py .
scp aiops-crawler:~/crawler-app/ansible_docs.json ../data/raw/
```

### 4. Mise en place de l'agent RAG

Sur le poste de travail :

```bash
cd ~/aiops-sentinel/agents/rag_agent
uv venv --python 3.11
source .venv/bin/activate
uv pip install mistralai qdrant-client sentence-transformers python-dotenv
```

### 5. Lancement

```bash
cd ~/aiops-sentinel/agents/rag_agent
source .venv/bin/activate
python main.py
```

## Configuration

Fichier `.env` (non versionne), a partir de `.env.example` :

```bash
MISTRAL_API_KEY=<cle API Mistral>
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=ansible_docs
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

## Verification

Interroger l'agent avec une question portant sur le contenu indexe, par
exemple : "Comment fonctionne un playbook Ansible ?". Une reponse valide
inclut un developpement structure du sujet et une citation explicite des
URLs sources en fin de reponse.

Etat de la collection Qdrant, consultable via l'API :

```bash
curl -s http://localhost:6333/collections/ansible_docs | python3 -m json.tool
```

## Depannage

**Connexion refusee depuis la VM vers Qdrant (port 6333)**

Cause : le trafic depuis le sous-reseau de la VM (zone firewalld `libvirt`)
n'est pas autorise par defaut.

Correction : voir Phase 2, section pare-feu.

**`httpcore.ReadTimeout` lors de l'indexation (`client.upsert`)**

Cause : delai d'attente par defaut du client Qdrant trop court pour un
envoi via le reseau virtualise de la VM.

Correction : instancier le client avec `timeout=60` :

```python
QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, timeout=60)
```

**`AttributeError: 'QdrantClient' object has no attribute 'search'`**

Cause : `qdrant-client==1.19.0` a remplace la methode `search()` par
`query_points()`.

Correction : utiliser `query_points(query=<vecteur>, ...)`, dont le resultat
expose les points via l'attribut `.points`.

**Avertissement de compatibilite de version au demarrage**

`UserWarning: Qdrant client version 1.19.0 is incompatible with server
version 1.11.3.` Sans effet observe sur le fonctionnement ; a surveiller
en cas d'anomalie, ou a resoudre en alignant les versions client/serveur.
