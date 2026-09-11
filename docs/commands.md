# Commandes utilisées — AIOps Sentinel

Documentation des commandes clés par phase, pour retrouver rapidement "comment j'avais fait".

## Phase 2 — Socle de données

### Création du dépôt Git

```bash
git init
git branch -m main
git remote add origin https://github.com/Med-ABDELGHANI/aiops-sentinel.git
```

### Corriger l'identité Git (si commit fait avec une identité auto-générée)

```bash
git config --global user.name "Ton Nom"
git config --global user.email "ton-email@exemple.com"
git commit --amend --reset-author --no-edit
git push --force-with-lease
```

### Générer un mot de passe fort pour PostgreSQL

```bash
openssl rand -base64 24
```

### Lancer PostgreSQL + Qdrant (podman-compose)

```bash
cd infra/compose
podman-compose up -d
podman-compose ps
```

### Vérifier l'état de santé d'un conteneur

```bash
podman inspect <nom_conteneur> --format '{{json .State.Health}}' | python3 -m json.tool
```

### Exécuter un script SQL dans le conteneur PostgreSQL

```bash
podman exec -i aiops-postgres psql -U aiops -d aiops_sentinel < db/schema.sql
```

- `exec` : exécute une commande dans un conteneur déjà lancé
- `-i` : garde l'entrée standard ouverte (nécessaire pour la redirection `<`)

### Lister les tables PostgreSQL

```bash
podman exec -it aiops-postgres psql -U aiops -d aiops_sentinel -c "\dt"
```

- `-it` : entrée standard + terminal virtuel, pour un affichage formaté
- `-c "..."` : exécute une seule commande puis quitte (`\dt` = liste des tables, commande interne psql)

### Tester que Qdrant répond

```bash
curl -s http://localhost:6333/healthz
```
