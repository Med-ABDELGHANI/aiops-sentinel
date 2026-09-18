# Phase 7 (partie 2) — LLM Serving local (llama.cpp)

## 1. Comprendre cette phase

### Besoin

Deployer un moteur d'inference LLM en local, heberge dans le cluster
Kubernetes, exposant une API compatible OpenAI, et l'integrer aux agents
IA du projet (Agent SQL, Agent RAG) en complement du fournisseur externe
(Mistral AI).

### Choix du moteur

Le moteur de reference pour le LLM Serving en production est vLLM. Son
backend CPU etant optimise pour les architectures x86 avec support
AVX-512 (non disponible sur le CPU cible), le choix s'est porte sur
llama.cpp, une alternative fonctionnellement equivalente, proposant une
image officielle prete a l'emploi et mieux adaptee a l'architecture CPU
disponible.

### Modele utilise

Qwen2.5-1.5B-Instruct, quantifie GGUF (Q4_K_M), ~1 Go.

### Architecture

```text
infra/k8s/llama-server/
|-- deployment.yaml
|-- service.yaml
```

Le service est expose via HAProxy sous le prefixe `/llm`, en complement
du routage par defaut vers l'API Gateway.

### Configuration reseau

| Service | Port |
|---------|------|
| llama-server (API) | 8080 |
| HAProxy -> llama-server | /llm/* -> 8080 |

## 2. Commandes utilisees

### Recuperation du modele

```bash
mkdir -p ~/models
cd ~/models
curl -L -o qwen2.5-1.5b-instruct-q4_k_m.gguf \
  https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf
```

### Validation initiale (conteneur Podman standalone)

```bash
podman pull ghcr.io/ggml-org/llama.cpp:server

podman run -d --name llama-vllm-test \
  -p 8080:8080 \
  -v ~/models:/models:z \
  ghcr.io/ggml-org/llama.cpp:server \
  -m /models/qwen2.5-1.5b-instruct-q4_k_m.gguf \
  --host 0.0.0.0 --port 8080 \
  -c 2048 --threads 4

curl -4 -s http://127.0.0.1:8080/health

curl -4 -s http://127.0.0.1:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "qwen2.5-1.5b", "messages": [{"role": "user", "content": "..."}]}'

podman stop llama-vllm-test
podman rm llama-vllm-test
```

### Manifestes Kubernetes

```bash
mkdir -p ~/aiops-sentinel/infra/k8s/llama-server

cat > ~/aiops-sentinel/infra/k8s/llama-server/deployment.yaml << 'YAML'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: llama-server
  namespace: aiops-sentinel
spec:
  replicas: 1
  selector:
    matchLabels:
      app: llama-server
  template:
    metadata:
      labels:
        app: llama-server
    spec:
      containers:
        - name: llama-server
          image: ghcr.io/ggml-org/llama.cpp:server
          args:
            - "-m"
            - "/models/qwen2.5-1.5b-instruct-q4_k_m.gguf"
            - "--host"
            - "0.0.0.0"
            - "--port"
            - "8080"
            - "-c"
            - "4096"
            - "--threads"
            - "4"
          ports:
            - containerPort: 8080
          volumeMounts:
            - name: models-volume
              mountPath: /models
      volumes:
        - name: models-volume
          hostPath:
            path: /home/mohamed/models
            type: Directory
YAML

cat > ~/aiops-sentinel/infra/k8s/llama-server/service.yaml << 'YAML'
apiVersion: v1
kind: Service
metadata:
  name: llama-server
  namespace: aiops-sentinel
spec:
  selector:
    app: llama-server
  ports:
    - port: 8080
      targetPort: 8080
  type: ClusterIP
YAML
```

### Deploiement

```bash
kubectl apply -f ~/aiops-sentinel/infra/k8s/llama-server/deployment.yaml
kubectl apply -f ~/aiops-sentinel/infra/k8s/llama-server/service.yaml

kubectl get pods -n aiops-sentinel | grep llama
kubectl logs -n aiops-sentinel -l app=llama-server --tail=20
```

### Mise a jour de la configuration (taille de contexte)

Le contexte a ete porte de 2048 a 4096 tokens pour couvrir les prompts
enrichis de l'Agent RAG (contexte documentaire + question).

```bash
kubectl apply -f ~/aiops-sentinel/infra/k8s/llama-server/deployment.yaml
kubectl rollout restart deployment llama-server -n aiops-sentinel
```

### Exposition via HAProxy

```bash
cat > ~/aiops-sentinel/infra/k8s/haproxy/haproxy.cfg << 'CFG'
global
    log stdout format raw local0

defaults
    log global
    mode http
    timeout connect 5s
    timeout client 30s
    timeout server 30s

frontend http_front
    bind *:80
    acl is_llm path_beg /llm
    use_backend llama_server_back if is_llm
    default_backend api_gateway_back

backend api_gateway_back
    server api_gateway api-gateway.aiops-sentinel.svc.cluster.local:8000

backend llama_server_back
    http-request set-path %[path,regsub(^/llm,,)]
    server llama_server llama-server.aiops-sentinel.svc.cluster.local:8080
CFG

kubectl delete configmap haproxy-config -n aiops-sentinel

kubectl create configmap haproxy-config -n aiops-sentinel \
  --from-file=haproxy.cfg=/home/mohamed/aiops-sentinel/infra/k8s/haproxy/haproxy.cfg

kubectl rollout restart deployment haproxy -n aiops-sentinel
```

### Verification via HAProxy

```bash
curl -4 -s http://localhost:30080/llm/health

curl -4 -s http://localhost:30080/llm/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "qwen2.5-1.5b", "messages": [{"role": "user", "content": "..."}]}'
```

### Integration aux agents IA

Copies dediees creees pour l'integration avec llama-server, en parallele
des versions originales (Mistral AI), laissees intactes.

```bash
cp -r ~/aiops-sentinel/agents/sql_agent ~/aiops-sentinel/agents/sql_agent_llama
rm -rf ~/aiops-sentinel/agents/sql_agent_llama/__pycache__

cp -r ~/aiops-sentinel/agents/rag_agent ~/aiops-sentinel/agents/rag_agent_llama
rm -rf ~/aiops-sentinel/agents/rag_agent_llama/__pycache__
```

Remplacement du SDK Mistral par le SDK OpenAI (applique sur chacun des
deux `main.py`) :

```bash
sed -i 's|from mistralai.client.sdk import Mistral|from openai import OpenAI|' <chemin>/main.py
sed -i 's|api_key_mistral = os.getenv("MISTRAL_API_KEY")|client = OpenAI(base_url="http://127.0.0.1:8080/v1", api_key="not-needed")|' <chemin>/main.py
sed -i '/^client = Mistral(api_key=api_key_mistral)$/d' <chemin>/main.py
sed -i 's|model = "mistral-small-2506"|model = "qwen2.5-1.5b"|' <chemin>/main.py
sed -i 's|client.chat.complete(|client.chat.completions.create(|g' <chemin>/main.py
```

Mise a jour des dependances :

```bash
sed -i '/^mistralai==/d' <chemin>/requirements.txt
echo "openai" >> <chemin>/requirements.txt
```

Creation des environnements Python dedies (uv, Python 3.11) :

```bash
cd ~/aiops-sentinel/agents/sql_agent_llama
uv venv venv-llama --python 3.11
source venv-llama/bin/activate
uv pip install -r requirements.txt

cd ~/aiops-sentinel/agents/rag_agent_llama
uv venv venv-llama --python 3.11
source venv-llama/bin/activate
uv pip install -r requirements.txt
```

Tunnels d'acces aux services internes (agents executes hors cluster) :

```bash
kubectl port-forward -n aiops-sentinel svc/llama-server 8080:8080
kubectl port-forward -n aiops-sentinel svc/postgres 5432:5432
kubectl port-forward -n aiops-sentinel svc/qdrant 6333:6333
```

Execution :

```bash
cd ~/aiops-sentinel/agents/sql_agent_llama
source venv-llama/bin/activate
python3 main.py
```

```bash
cd ~/aiops-sentinel/agents/rag_agent_llama
source venv-llama/bin/activate
python3 main.py
```

## 3. Resultats

- Agent SQL + llama-server : pipeline technique valide (connexion,
  requete, reponse fonctionnelle).
- Agent RAG + llama-server : pipeline valide, reponse coherente et
  contextualisee a partir des passages de documentation Ansible
  recuperes via Qdrant.

## 4. Fichiers crees/modifies

| Fichier | Description |
|---------|--------------|
| infra/k8s/llama-server/deployment.yaml | Deploiement Kubernetes du service llama-server |
| infra/k8s/llama-server/service.yaml | Service Kubernetes exposant llama-server en interne |
| infra/k8s/haproxy/haproxy.cfg | Ajout de la regle de routage /llm vers llama-server |
| agents/sql_agent_llama/ | Copie adaptee de l'agent SQL pour llama-server |
| agents/rag_agent_llama/ | Copie adaptee de l'agent RAG pour llama-server |
