# Phase 7 — Observabilite (Splunk)

## 1. Comprendre cette phase

### Besoin

Les services du projet (agents, serveurs MCP, API) affichent leurs logs
uniquement dans leur terminal respectif, sans centralisation. Cette phase
met en place Splunk pour collecter, indexer et rendre consultable
l'ensemble de ces logs depuis une interface unique.

### Architecture

```text
infra/observability/
|-- docker-compose.yml   (service Splunk)
|-- .env.example
```

Splunk expose deux ports distincts : l'interface web (consultation,
recherche, tableaux de bord) et le HEC - HTTP Event Collector (reception
programmatique de logs envoyes par les services du projet).

### Configuration reseau

Le port web de Splunk est mappe en 8010 sur l'hote (au lieu du port 8000
par defaut de l'image), afin d'eviter tout conflit avec l'API FastAPI
(Phase 6), qui utilise elle-meme le port 8000.

| Service | Port hote | Port interne |
|---------|-----------|---------------|
| Splunk (web) | 8010 | 8000 |
| Splunk (HEC) | 8088 | 8088 |

## 2. Commandes utilisees

### Generation des identifiants

```bash
cd infra/observability
openssl rand -base64 16   # mot de passe admin Splunk
openssl rand -hex 24      # token HEC
```

### Demarrage

```bash
cd infra/observability
podman-compose up -d
```

Le tout premier demarrage prend plusieurs minutes (initialisation interne
Ansible de l'image Splunk).

### Verification

```bash
podman-compose ps
curl http://localhost:8010
```

### Acces a l'interface

```text
http://localhost:8010
```
