# Phase 4 — Agent RAG documentation

## 1. Comprendre cette phase

### Besoin

L'agent SQL (Phase 3) sait repondre a des questions sur des donnees
structurees, mais il est incapable de repondre a une question portant sur
de la documentation technique en texte libre, par exemple "comment
fonctionne un playbook Ansible ?". Cette phase construit un second agent,
capable de retrouver des passages de documentation pertinents par sens
(et non par mots-cles exacts), et de generer une reponse ancree dans ces
passages plutot que dans la memoire generale du modele.

### Principe general : RAG (Retrieval-Augmented Generation)

Chaque document est decoupe en segments, et chaque segment est transforme
en vecteur numerique (embedding) qui represente son sens. Ces vecteurs
sont stockes dans une base specialisee (Qdrant). A chaque question, la
question elle-meme est transformee en vecteur de la meme maniere, puis
comparee aux vecteurs stockes pour retrouver les segments les plus
proches semantiquement. Ces segments sont ensuite fournis au modele de
langage comme contexte, avec pour consigne de repondre uniquement a
partir d'eux.

### Architecture et flux de donnees

```text
crawler/crawl_ansible_docs.py
  -> data/raw/ansible_docs.json          (pages collectees, brutes)
  -> crawler/index_ansible_docs.py
  -> Qdrant, collection "ansible_docs"    (segments vectorises)
  -> agents/rag_agent/main.py              (recherche + generation)
```

La collecte et l'indexation sont executees une fois, ou a chaque mise a
jour de la documentation source. L'agent, lui, interroge Qdrant a chaque
question ; contrairement a l'agent SQL, les donnees consultees ne sont a
jour qu'au moment de la derniere indexation, pas en temps reel.

### Les fichiers de cette phase et leur role

**`crawler/crawl_ansible_docs.py`**
Utilise Crawl4AI, sur la VM dediee, pour collecter le contenu de trois
pages de la documentation officielle Ansible et le convertir en texte
markdown propre. Produit `ansible_docs.json` : pour chaque page, son URL,
son titre, et son contenu.

**`crawler/index_ansible_docs.py`**
Lit ce fichier JSON, decoupe le contenu de chaque page en segments
d'environ 800 caracteres (sur les frontieres de paragraphes, via la
fonction `chunk_text`), transforme chaque segment en vecteur via le
modele `all-MiniLM-L6-v2`, et indexe l'ensemble dans une collection
Qdrant nommee `ansible_docs`, avec le texte original et sa source
conserves comme metadonnees.

**`agents/rag_agent/main.py`** — fonctions principales

`search_docs(query, top_k)` : transforme la question en vecteur, interroge
Qdrant pour retrouver les segments les plus proches semantiquement (par
defaut, les trois meilleurs), et renvoie pour chacun son texte, son URL
source, son titre et son score de similarite.

`build_prompt(query, chunks)` : assemble un texte unique destine au
modele de langage, combinant les segments trouves (avec leur source
indiquee) et la question posee, suivi d'une consigne explicite de
repondre uniquement a partir de ces extraits.

`system_prompt` : impose a l'agent de ne repondre qu'a partir du contexte
fourni, d'indiquer clairement une insuffisance d'information plutot que
d'inventer, et de toujours citer les sources utilisees en fin de reponse.

Classe `RagConversation` : a chaque question, appelle `search_docs` puis
`build_prompt`, puis effectue un unique appel au modele de langage (sans
mecanisme de decision d'outils, contrairement a l'agent SQL, puisqu'une
seule action est ici possible : la recherche documentaire).

### Relation avec l'agent SQL (Phase 3)

Les deux agents partagent la meme logique generale (question -> recherche
d'information -> generation de reponse), mais different dans leur source
de verite : l'agent SQL interroge PostgreSQL en temps reel, tandis que
l'agent RAG interroge un instantane fige de la documentation, constitue
lors de la derniere indexation.

## 2. Commandes utilisees

### Collecte de la documentation source (sur la VM)

```bash
cd ~/crawler-app
source .venv/bin/activate
python crawl_ansible_docs.py
```

### Indexation dans Qdrant (sur la VM)

```bash
uv pip install sentence-transformers qdrant-client
python index_ansible_docs.py
```

### Recuperation des artefacts vers le depot (sur le poste de travail)

```bash
cd ~/aiops-sentinel/crawler
scp aiops-crawler:~/crawler-app/crawl_ansible_docs.py .
scp aiops-crawler:~/crawler-app/index_ansible_docs.py .
scp aiops-crawler:~/crawler-app/ansible_docs.json ../data/raw/
```

### Mise en place de l'agent RAG (sur le poste de travail)

```bash
cd ~/aiops-sentinel/agents/rag_agent
uv venv --python 3.11
source .venv/bin/activate
uv pip install mistralai qdrant-client sentence-transformers python-dotenv
uv pip freeze > requirements.txt
```

### Lancement

```bash
cd ~/aiops-sentinel/agents/rag_agent
source .venv/bin/activate
python main.py
```

### Verification de l'etat de la collection Qdrant

```bash
curl -s http://localhost:6333/collections/ansible_docs | python3 -m json.tool
```
