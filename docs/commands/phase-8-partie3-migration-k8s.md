# Phase 8 (partie 3) — Migration de l'architecture Kubernetes vers Oracle Cloud

## 1. Comprendre cette phase

### Besoin

Reproduire sur la VM Oracle l'architecture applicative complete
(bases de donnees, agents, API Gateway, LLM serving) prealablement
deployee en local, a partir du code source verse sur GitHub.

### Principe

Les images de conteneurs construites localement (via Podman) ne sont
pas transferables automatiquement d'une machine a l'autre. Chaque
environnement d'execution doit reconstruire ses propres images a
partir du code source. Les images officielles (PostgreSQL, Qdrant)
sont en revanche telechargees automatiquement par Kubernetes lors du
premier deploiement.

### Architecture cible

7 services deployes dans le namespace `aiops-sentinel` :

| Service | Origine de l'image | Role |
|---|---|---|
| postgres | Image officielle (Docker Hub) | Base de donnees relationnelle |
| qdrant | Image officielle (Docker Hub) | Base vectorielle |
| sql-server | Construite (Dockerfile) | Serveur MCP agent SQL |
| rag-server | Construite (Dockerfile) | Serveur MCP agent RAG |
| api-gateway | Construite (Dockerfile) | API FastAPI, point d'entree |
| llama-server | Image officielle (llama.cpp) | Moteur d'inference LLM local |
| haproxy | Image officielle | Routage / point d'entree unique |

## 2. Commandes utilisees

### Installation des outils de base

```bash
sudo dnf update -y
sudo dnf install -y git podman
```

### Installation de k3s

```bash
curl -sfL https://get.k3s.io | sh -
sudo systemctl status k3s
```

### Configuration de l'acces kubectl sans privileges root

```bash
mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown $(id -u):$(id -g) ~/.kube/config
chmod 600 ~/.kube/config
echo 'export KUBECONFIG=~/.kube/config' >> ~/.bashrc
source ~/.bashrc
kubectl get nodes
```

Resultat :
```text
NAME                  STATUS   ROLES           AGE   VERSION
aiops-sentinel-prod   Ready    control-plane   2m    v1.36.4+k3s1
```

### Recuperation du code source

```bash
git clone https://github.com/Med-ABDELGHANI/aiops-sentinel.git
cd aiops-sentinel
```

### Creation du namespace

```bash
kubectl create namespace aiops-sentinel
```

### Reconstruction des images applicatives

```bash
cd ~/aiops-sentinel/api
podman build -t localhost/api-gateway:latest .

cd ~/aiops-sentinel/mcp_servers/sql_server
podman build -t localhost/sql-server:latest .

cd ~/aiops-sentinel/mcp_servers/rag_server
podman build -f Dockerfile.oracle -t localhost/rag-server:latest .
```

Note : l'image `rag-server` est construite a partir d'un Dockerfile
dedie (`Dockerfile.oracle`), qui installe une version des dependances
Python optimisee pour l'architecture ARM sans acceleration GPU,
l'instance Oracle ne disposant pas de carte graphique dediee.

Verification :
```bash
podman images
```

```text
REPOSITORY                TAG         SIZE
localhost/sql-server      latest      277 MB
localhost/api-gateway     latest      327 MB
localhost/rag-server      latest      1.51 GB
docker.io/library/python  3.11-slim   155 MB
```

### Import des images dans le registre k3s

k3s utilise `containerd` comme moteur de conteneurs, distinct du
stockage local de Podman. Les images construites doivent etre
importees explicitement :

```bash
podman save localhost/api-gateway:latest | sudo /usr/local/bin/k3s ctr images import -
podman save localhost/sql-server:latest | sudo /usr/local/bin/k3s ctr images import -
podman save localhost/rag-server:latest | sudo /usr/local/bin/k3s ctr images import -
```

### Creation des secrets Kubernetes

Les identifiants sensibles (mots de passe, cles API) ne sont jamais
verses dans le depot Git et doivent etre recrees manuellement sur
chaque environnement :

```bash
kubectl create secret generic postgres-secret \
  --namespace=aiops-sentinel \
  --from-literal=POSTGRES_USER=aiops \
  --from-literal=POSTGRES_PASSWORD=<mot_de_passe> \
  --from-literal=POSTGRES_DB=aiops_sentinel

kubectl create secret generic sql-server-secret \
  --namespace=aiops-sentinel \
  --from-literal=PG_ADMIN_USER=aiops \
  --from-literal=PG_ADMIN_PASSWORD=<mot_de_passe> \
  --from-literal=PG_READONLY_USER=infra_readonly \
  --from-literal=PG_READONLY_PASSWORD=<mot_de_passe>

kubectl create secret generic api-gateway-secret \
  --namespace=aiops-sentinel \
  --from-literal=PG_ADMIN_PASSWORD=<mot_de_passe> \
  --from-literal=MISTRAL_API_KEY=<cle_api> \
  --from-literal=SPLUNK_HEC_TOKEN=<token>
```

### Deploiement des services de donnees

```bash
kubectl apply -f infra/k8s-oracle/postgres/
kubectl apply -f infra/k8s-oracle/qdrant/
```

### Deploiement des services applicatifs

```bash
kubectl apply -f infra/k8s-oracle/sql-server/
kubectl apply -f infra/k8s-oracle/rag-server/
kubectl apply -f infra/k8s-oracle/api-gateway/
```

### Deploiement du LLM serving local

Le modele est telecharge directement sur la VM Oracle, independamment
de la copie locale sur PC :

```bash
mkdir -p ~/models
cd ~/models
curl -L -o qwen2.5-1.5b-instruct-q4_k_m.gguf \
  https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf

cd ~/aiops-sentinel
kubectl apply -f infra/k8s-oracle/llama-server/
```

### Verification finale

```bash
kubectl get pods -n aiops-sentinel
```

Resultat :
```text
NAME                            READY   STATUS    RESTARTS   AGE
api-gateway-68b6664d98-vnmq2    1/1     Running   0          7m
llama-server-7d8984d9cc-6qn2z   1/1     Running   0          38s
postgres-688b48df8f-xldlh       1/1     Running   0          37m
qdrant-7b8457bb94-xdrqq         1/1     Running   0          37m
rag-server-d5cc5f756-f76n6      1/1     Running   0          7m
sql-server-58b89d5887-dj72z     1/1     Running   0          7m
```

## 3. Resultat

L'ensemble des 6 services applicatifs et de donnees est deploye et
operationnel sur le cluster k3s de la VM Oracle. La mise en place du
point d'entree HAProxy est traitee dans la partie 4.

## 4. Fichiers de reference

Les manifestes Kubernetes specifiques a Oracle sont regroupes dans
`infra/k8s-oracle/`, distinct de `infra/k8s/` (deploiement local sur
PC), pour permettre le maintien des deux configurations en parallele.
