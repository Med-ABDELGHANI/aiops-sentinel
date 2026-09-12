# Phase 3 — Agent SQL infra

## 1. Comprendre cette phase

### Besoin

L'inventaire d'infrastructure (Phase 2) est stocke dans PostgreSQL, mais
personne ne veut interroger une base de donnees en ecrivant du SQL a la
main a chaque question. Cette phase construit un agent capable de
comprendre une question en langage naturel, de decouvrir lui-meme la
structure reelle de la base, de generer la requete SQL correspondante,
de l'executer, et de formuler une reponse comprehensible.

### Principe general : le function calling

Le modele de langage ne sait produire que du texte ; il ne peut pas se
connecter a une base de donnees. Le function calling est le mecanisme qui
lui permet de demander l'execution d'une fonction ecrite par le
developpeur : le modele decrit quel outil il souhaite utiliser et avec
quels parametres, le programme execute reellement cette fonction, puis
transmet le resultat au modele pour qu'il redige sa reponse finale.

### Architecture

```text
Question utilisateur
  -> Routeur : quel(s) outil(s) sont necessaires ?
  -> Boucle d'appels d'outils (jusqu'a decision d'arret par le modele) :
       get_pg_schema          : decouvre la structure reelle de la base
       execute_sql_query       : execute une requete SELECT et renvoie le resultat
       check_server_reachability : teste une connexion TCP vers un hote/port
  -> Reponse finale en langage naturel
```

L'agent se connecte directement a PostgreSQL a chaque question ; il n'y a
pas d'etape de preparation intermediaire comme pour l'agent RAG (Phase 4).
Les donnees interrogees sont donc toujours a jour.

### Le fichier `agents/sql_agent/main.py` et ses roles

**Configuration (`PG_HOST`, `PG_ADMIN_USER`, `PG_READONLY_USER`, etc.)**
Toutes les valeurs de connexion sont lues depuis le fichier `.env`, pour
qu'aucun identifiant ne soit ecrit en dur dans le code.

**`system_prompt`**
Fixe les regles de comportement de l'agent : toujours decouvrir le schema
avant de generer du SQL, ne jamais inventer un nom de table ou de colonne,
ne generer que des requetes `SELECT` (jamais d'ecriture ou de suppression),
et toujours presenter la requete utilisee ainsi que le resultat obtenu.

**`get_pg_schema(...)`**
Se connecte a PostgreSQL, liste les bases existantes, puis pour chacune,
interroge la vue systeme `information_schema.columns` afin de construire
un dictionnaire complet des schemas, tables et colonnes reels. Utilise
l'utilisateur administrateur, car cette operation ne touche qu'a des
metadonnees, jamais aux donnees elles-memes.

**`execute_sql_query(query, ...)`**
Execute une requete SQL fournie par le modele, apres avoir verifie qu'elle
commence bien par `SELECT`. Se connecte avec l'utilisateur `infra_readonly`
(droits de lecture seule), de sorte qu'une requete de modification ne
puisse aboutir meme si elle passait la premiere verification.

**`check_server_reachability(host, port, ...)`**
Tente une connexion TCP reelle vers un hote et un port donnes, et renvoie
si la connexion a reussi ou echoue. Independant de PostgreSQL ; utile pour
verifier l'etat reseau d'un serveur ou service de l'inventaire.

**`functions` et `tools`**
`functions` associe le nom textuel de chaque outil a la fonction Python
reelle correspondante. `tools` decrit chaque outil au format attendu par
l'API Mistral (nom, description, parametres), sans jamais exposer le code
source au modele.

**Classe `Conversation`**
Orchestre l'ensemble : un premier appel isole demande au modele quels
outils sont necessaires pour la question posee ; une boucle (limitee a
cinq iterations) enchaine ensuite les appels d'outils tant que le modele
en demande, en lui laissant la possibilite de s'arreter de lui-meme des
qu'il dispose de suffisamment d'informations ; un dernier appel, sans
outil, produit la reponse finale en langage naturel.

## 2. Commandes utilisees

### Mise en place de l'environnement Python

```bash
cd agents/sql_agent
uv venv --python 3.11
source .venv/bin/activate
uv pip install mistralai psycopg2-binary python-dotenv
```

### Figer les dependances

```bash
uv pip freeze > requirements.txt
```

### Lancement

```bash
cd agents/sql_agent
source .venv/bin/activate
python main.py
```
