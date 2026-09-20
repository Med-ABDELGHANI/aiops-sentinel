# AIOps Sentinel

Plateforme d'agents IA en langage naturel pour interroger une infrastructure :
inventaire structuré (PostgreSQL, Agent SQL) et documentation technique
collectee automatiquement (Crawl4AI, indexee dans Qdrant, Agent RAG).

Deploiement production : https://aiops-sentinel.duckdns.org

## Stack technique

Python, FastAPI, PostgreSQL, Qdrant, Mistral AI, Crawl4AI, FastMCP,
Splunk, llama.cpp, Podman, Kubernetes (k3s), HAProxy, Oracle Cloud
Infrastructure, Let's Encrypt.

## Statut

Projet complet, deploye en production sur Oracle Cloud.

- [x] Phase 1 — Cadrage & architecture
- [x] Phase 2 — Socle de donnees (PostgreSQL + Qdrant + Crawl4AI)
- [x] Phase 3 — Agent SQL infrastructure (function calling)
- [x] Phase 4 — Agent RAG documentation
- [x] Phase 5 — Orchestration multi-agents (MCP)
- [x] Phase 6 — API Gateway (FastAPI + Swagger)
- [x] Phase 7 — Observabilite (Splunk) et LLM Serving local (llama.cpp)
- [x] Phase 8 — Deploiement Kubernetes local (k3s) et migration Oracle Cloud (HTTPS)

## Documentation

Documentation detaillee de chaque phase (comprehension, architecture,
commandes) disponible dans `docs/commands/`. Resultats et captures
d'ecran dans `docs/results.md`.
