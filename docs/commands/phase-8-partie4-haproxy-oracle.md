# Phase 8 (partie 4) — Mise en place de HAProxy comme point d'entree sur Oracle Cloud

## 1. Comprendre cette phase

### Besoin

Exposer l'ensemble de l'architecture applicative via un point d'entree
unique et stable, accessible depuis l'exterieur du cluster sans
tunnel temporaire, en reprenant le role deja tenu par HAProxy dans le
deploiement local.

### Point d'attention specifique a Oracle

k3s installe par defaut Traefik comme controleur d'entree (ingress
controller), qui reserve automatiquement le port 80 au niveau du
cluster. Ce comportement, deja rencontre et resolu lors du deploiement
local, doit etre traite de la meme maniere : desinstallation de
Traefik au profit de HAProxy comme point d'entree unique.

### Architecture reseau retenue

Le pod HAProxy est configure avec l'option `hostPort`, qui lie
directement les ports du conteneur aux ports correspondants de la VM
hote. Cette approche permet d'exposer HAProxy sur les ports standards
(80, puis 443 en partie 5), en complement de l'exposition NodePort
deja en place sur le port 30080.

## 2. Commandes utilisees

### Desinstallation de Traefik

```bash
kubectl -n kube-system delete helmchart traefik
kubectl -n kube-system delete helmchart traefik-crd
```

Verification :
```bash
kubectl get pods -A | grep -i traefik
```
(aucun resultat attendu)

### Configuration du service HAProxy (NodePort)

`infra/k8s-oracle/haproxy/service.yaml` :
```yaml
apiVersion: v1
kind: Service
metadata:
  name: haproxy
  namespace: aiops-sentinel
spec:
  type: NodePort
  selector:
    app: haproxy
  ports:
    - port: 80
      targetPort: 80
      nodePort: 30080
```

### Configuration du deploiement HAProxy avec hostPort

`infra/k8s-oracle/haproxy/deployment.yaml` :
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: haproxy
  namespace: aiops-sentinel
spec:
  replicas: 1
  selector:
    matchLabels:
      app: haproxy
  template:
    metadata:
      labels:
        app: haproxy
    spec:
      containers:
        - name: haproxy
          image: docker.io/library/haproxy:2.9-alpine
          ports:
            - containerPort: 80
              hostPort: 80
          volumeMounts:
            - name: haproxy-config-volume
              mountPath: /usr/local/etc/haproxy/haproxy.cfg
              subPath: haproxy.cfg
      volumes:
        - name: haproxy-config-volume
          configMap:
            name: haproxy-config
```

### Deploiement

```bash
cd ~/aiops-sentinel/infra/k8s-oracle/haproxy

kubectl create configmap haproxy-config \
  --namespace=aiops-sentinel \
  --from-file=haproxy.cfg

kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
```

### Verification de l'ensemble du cluster

```bash
kubectl get pods -n aiops-sentinel
```

Resultat :
```text
NAME                            READY   STATUS    RESTARTS   AGE
api-gateway-68b6664d98-vnmq2    1/1     Running   0          7m
haproxy-7df8d899c-dl7gg         1/1     Running   0          3m
llama-server-7d8984d9cc-6qn2z   1/1     Running   0          38s
postgres-688b48df8f-xldlh       1/1     Running   0          37m
qdrant-7b8457bb94-xdrqq         1/1     Running   0          37m
rag-server-d5cc5f756-f76n6      1/1     Running   0          7m
sql-server-58b89d5887-dj72z     1/1     Running   0          7m
```

### Verification de l'acces, local et externe

```bash
curl -s http://localhost:30080/
```
```text
{"status":"ok","service":"AIOps Sentinel API"}
```

Depuis un poste externe :
```bash
curl -s http://141.145.215.142:30080/
```
```text
{"status":"ok","service":"AIOps Sentinel API"}
```

## 3. Resultat

HAProxy est operationnel comme point d'entree unique du cluster,
accessible depuis Internet sur le port 30080 (NodePort) et sur le port
80 (hostPort), routant les requetes vers l'API Gateway par defaut et
vers le service LLM local sous le prefixe `/llm`.

## 4. Points de reference

| Element | Valeur |
|---|---|
| Point d'entree HTTP | http://141.145.215.142:30080/ |
| Point d'entree HTTP (port standard) | http://141.145.215.142:80/ |
| Documentation Swagger | .../docs |
| Interface LLM local | .../llm/ |
