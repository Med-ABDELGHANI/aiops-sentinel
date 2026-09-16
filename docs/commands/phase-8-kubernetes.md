# Phase 8 — Deploiement Kubernetes

## 1. Comprendre cette phase

### Besoin

Les phases precedentes ont produit une architecture applicative complete
(bases de donnees, agents, orchestrateur, API), geree manuellement via
Podman et des processus lances individuellement. Cette phase migre cette
architecture vers Kubernetes, l'orchestrateur standard de l'industrie,
pour beneficier d'une gestion declarative, d'un redemarrage automatique
en cas de defaillance, et d'un point d'entree unique et stable.

### Principe general : Kubernetes

Kubernetes automatise le deploiement, la surveillance et la recuperation
d'applications conteneurisees. Plutot que de lancer et surveiller
manuellement chaque conteneur (comme avec Podman), on decrit dans des
fichiers YAML l'etat souhaite (quelle image, combien de copies, quelles
ressources), et Kubernetes maintient cet etat en permanence, y compris en
redemarrant automatiquement un conteneur qui viendrait a planter.

Sur ce projet, k3s (une distribution legere de Kubernetes, adaptee aux
machines a ressources limitees) est utilise en cluster local a un seul
noeud. Les concepts manipules (Deployment, Service, PersistentVolumeClaim,
Secret, ConfigMap) restent identiques a ceux d'un cluster de production a
plusieurs noeuds.

### Architecture generale

```text
Client (navigateur, curl)
    |
    v
HAProxy (NodePort 30080) -- point d'entree unique
    |
    v
API Gateway (port 8000)
    |
    +-- CRUD --> PostgreSQL (port 5432)
    |
    +-- /chat --> Serveur MCP SQL (port 8001) --> PostgreSQL
              --> Serveur MCP RAG (port 8002) --> Qdrant (port 6333)
```

Splunk reste heberge separement via Podman, en dehors du perimetre de
cette migration.

### Deux categories de composants, deux approches differentes

**Logiciels deja publies (images officielles existantes)** : PostgreSQL,
Qdrant, HAProxy. Aucune construction d'image necessaire ; on utilise
directement l'image publique (ex. `docker.io/library/postgres:16.4`),
combinee a un PersistentVolumeClaim (stockage qui survit au redemarrage
du pod) pour les deux premiers.

**Code propre au projet (aucune image existante)** : le serveur MCP SQL,
le serveur MCP RAG, l'API Gateway. Chacun necessite un `Dockerfile` (la
recette de construction d'image a partir du code source), puis une
construction (`podman build`) et un transfert vers le registre d'images
interne de k3s, distinct de celui de Podman.

### Les fichiers et leur role

**`infra/k8s/postgres/`, `infra/k8s/qdrant/`**
Chacun contient `pvc.yaml` (stockage persistant), `deployment.yaml`
(execution du conteneur), `service.yaml` (adresse stable interne au
cluster). Les identifiants PostgreSQL sont fournis via un Secret
Kubernetes (`postgres-secret`), jamais ecrits en clair dans un fichier
versionne.

**`mcp_servers/sql_server/Dockerfile`, `mcp_servers/rag_server/Dockerfile`,
`api/Dockerfile`**
Recette de construction d'image pour chaque composant developpe dans le
cadre du projet. Structure identique : image de base Python allegee,
installation des dependances, copie du code, commande de demarrage.

**`infra/k8s/sql-server/`, `infra/k8s/rag-server/`, `infra/k8s/api-gateway/`**
Manifests de deploiement pour chaque service applicatif. Chacun reference
l'image importee localement (`imagePullPolicy: Never`, empechant
Kubernetes de tenter un telechargement depuis un registre externe), et
utilise le nom des Services internes (ex. `postgres`, `qdrant`) plutot
que `localhost` pour la communication inter-services, chaque composant
etant desormais un pod distinct au sein du cluster.

**`infra/k8s/haproxy/`**
Configuration HAProxy (`haproxy.cfg`, integree via une ConfigMap),
manifests de deploiement et de service. Le Service HAProxy utilise le
type `NodePort` (plutot que `ClusterIP`), rendant l'ensemble de
l'architecture accessible depuis l'exterieur du cluster sur un port fixe,
sans tunnel temporaire.

### Point d'entree HAProxy

k3s installe par defaut Traefik comme controleur d'entree (ingress
controller). Celui-ci a ete desinstalle au profit de HAProxy, utilise
comme point d'entree unique du cluster.

## 2. Commandes utilisees

### Installation de k3s

```bash
curl -sfL https://get.k3s.io | sh -
sudo systemctl status k3s
```

### Configuration de l'acces kubectl

```bash
mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown $(id -u):$(id -g) ~/.kube/config
export KUBECONFIG=~/.kube/config
echo 'export KUBECONFIG=~/.kube/config' >> ~/.bashrc
kubectl get nodes
```

### Creation du namespace dedie

```bash
kubectl create namespace aiops-sentinel
```

### Desactivation de Traefik

```bash
kubectl get pods -n kube-system
sudo /usr/local/bin/k3s kubectl delete helmchart traefik traefik-crd -n kube-system
kubectl get pods -n kube-system
```

### Migration de PostgreSQL

```bash
kubectl create secret generic postgres-secret \
  --namespace=aiops-sentinel \
  --from-literal=POSTGRES_USER=aiops \
  --from-literal=POSTGRES_PASSWORD=<mot_de_passe> \
  --from-literal=POSTGRES_DB=aiops_sentinel

kubectl apply -f infra/k8s/postgres/pvc.yaml
kubectl apply -f infra/k8s/postgres/deployment.yaml
kubectl apply -f infra/k8s/postgres/service.yaml

# Chargement du schema et des donnees
kubectl cp db/schema.sql aiops-sentinel/<pod>:/tmp/schema.sql
kubectl cp db/seed.sql aiops-sentinel/<pod>:/tmp/seed.sql
kubectl cp db/create_readonly_user.sql aiops-sentinel/<pod>:/tmp/create_readonly_user.sql

kubectl exec -it -n aiops-sentinel deployment/postgres -- psql -U aiops -d aiops_sentinel -f /tmp/schema.sql
kubectl exec -it -n aiops-sentinel deployment/postgres -- psql -U aiops -d aiops_sentinel -f /tmp/seed.sql
kubectl exec -it -n aiops-sentinel deployment/postgres -- psql -U aiops -d aiops_sentinel -f /tmp/create_readonly_user.sql

# Verification
kubectl exec -it -n aiops-sentinel deployment/postgres -- psql -U aiops -d aiops_sentinel -c "\dt"
```

Une fois valide, l'ancien conteneur Podman est arrete :

```bash
cd infra/database
podman-compose stop postgres
```

### Migration de Qdrant

```bash
kubectl apply -f infra/k8s/qdrant/pvc.yaml
kubectl apply -f infra/k8s/qdrant/deployment.yaml
kubectl apply -f infra/k8s/qdrant/service.yaml

# Reindexation de la documentation Ansible (fichier deja collecte en Phase 4)
kubectl port-forward -n aiops-sentinel svc/qdrant 7333:6333 &
cd data/raw
QDRANT_HOST=localhost QDRANT_PORT=7333 python3 ../../crawler/index_ansible_docs.py

# Verification
curl -s http://localhost:7333/collections/ansible_docs
```

Une fois valide :

```bash
cd infra/database
podman-compose stop qdrant
```

### Construction et deploiement du serveur MCP SQL

```bash
cd mcp_servers/sql_server
podman build -t sql-server:latest .
podman save sql-server:latest -o /tmp/sql-server.tar
sudo /usr/local/bin/k3s ctr images import /tmp/sql-server.tar

kubectl create secret generic sql-server-secret \
  --namespace=aiops-sentinel \
  --from-literal=PG_ADMIN_USER=aiops \
  --from-literal=PG_ADMIN_PASSWORD=<mot_de_passe> \
  --from-literal=PG_READONLY_USER=infra_readonly \
  --from-literal=PG_READONLY_PASSWORD=<mot_de_passe>

kubectl apply -f infra/k8s/sql-server/deployment.yaml
kubectl apply -f infra/k8s/sql-server/service.yaml
```

### Construction et deploiement du serveur MCP RAG

```bash
cd mcp_servers/rag_server
podman build -t rag-server:latest .
podman save rag-server:latest -o /tmp/rag-server.tar
sudo /usr/local/bin/k3s ctr images import /tmp/rag-server.tar

kubectl apply -f infra/k8s/rag-server/deployment.yaml
kubectl apply -f infra/k8s/rag-server/service.yaml
```

### Construction et deploiement de l'API Gateway

```bash
cd api
podman build -t api-gateway:latest .
podman save api-gateway:latest -o /tmp/api-gateway.tar
sudo /usr/local/bin/k3s ctr images import /tmp/api-gateway.tar

kubectl create secret generic api-gateway-secret \
  --namespace=aiops-sentinel \
  --from-literal=PG_ADMIN_PASSWORD=<mot_de_passe> \
  --from-literal=MISTRAL_API_KEY=<cle_api> \
  --from-literal=SPLUNK_HEC_TOKEN=<token>

kubectl apply -f infra/k8s/api-gateway/deployment.yaml
kubectl apply -f infra/k8s/api-gateway/service.yaml
```

### Mise en place de HAProxy

```bash
cd infra/k8s/haproxy
kubectl create configmap haproxy-config \
  --namespace=aiops-sentinel \
  --from-file=haproxy.cfg

kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
```

Mise a jour de la configuration apres modification du fichier source :

```bash
kubectl create configmap haproxy-config \
  --namespace=aiops-sentinel \
  --from-file=haproxy.cfg \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl rollout restart deployment haproxy -n aiops-sentinel
```

### Verification de l'ensemble

```bash
kubectl get pods -n aiops-sentinel
kubectl get secrets -n aiops-sentinel
kubectl get configmap -n aiops-sentinel

# Acces via HAProxy, sans tunnel
curl -s http://localhost:30080/servers/
curl -s -X POST http://localhost:30080/chat/ \
  -H "Content-Type: application/json" \
  -d '{"question": "Combien de serveurs sont actifs ?"}'
```

### Test ponctuel d'un composant via tunnel (debogage)

```bash
kubectl port-forward -n aiops-sentinel svc/<service> <port_local>:<port_service> &
# ... test ...
kill %1
```
