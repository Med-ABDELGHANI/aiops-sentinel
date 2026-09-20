# Phase 8 (partie 5) — Nom de domaine et certificat HTTPS (Let's Encrypt)

## 1. Comprendre cette phase

### Besoin

Rendre l'architecture accessible via un nom de domaine plutot qu'une
adresse IP brute, et securiser les echanges avec un certificat HTTPS
valide, reconnu par les navigateurs.

### Choix techniques

**Nom de domaine** : DuckDNS, service de DNS dynamique gratuit,
associe a l'adresse IP publique de l'instance Oracle.

**Certificat HTTPS** : Let's Encrypt, autorite de certification
gratuite, via l'outil Certbot en methode de validation HTTP standalone
(le domaine doit repondre sur le port 80 le temps de la validation).

### Architecture retenue

Le certificat est genere directement sur la VM Oracle avec Certbot,
puis combine (certificat + cle privee) dans un fichier unique au
format attendu par HAProxy. Ce fichier est monte dans le pod HAProxy
via un volume `hostPath`, et HAProxy est configure pour ecouter
egalement sur le port 443 en TLS.

## 2. Commandes utilisees

### Creation du nom de domaine (DuckDNS)

Compte cree sur duckdns.org (authentification via GitHub), sous-domaine
enregistre :

```text
aiops-sentinel.duckdns.org -> 141.145.215.142
```

Verification de la resolution DNS :
```bash
nslookup aiops-sentinel.duckdns.org
```
```text
Name:    aiops-sentinel.duckdns.org
Address: 141.145.215.142
```

### Installation de Certbot

Le depot EPEL, preinstalle sur Oracle Linux mais desactive par defaut,
doit etre active prealablement :

```bash
sudo dnf config-manager --set-enabled ol9_developer_EPEL
sudo dnf install -y certbot
```

### Generation du certificat

HAProxy est temporairement arrete pour liberer le port 80, necessaire
a la validation standalone de Certbot :

```bash
kubectl scale deployment haproxy -n aiops-sentinel --replicas=0

sudo certbot certonly --standalone \
  -d aiops-sentinel.duckdns.org \
  --non-interactive --agree-tos \
  --email <email>
```

Resultat :
```text
Successfully received certificate.
Certificate is saved at: /etc/letsencrypt/live/aiops-sentinel.duckdns.org/fullchain.pem
Key is saved at:         /etc/letsencrypt/live/aiops-sentinel.duckdns.org/privkey.pem
This certificate expires on 2026-12-19.
Certbot has set up a scheduled task to automatically renew this certificate in the background.
```

### Preparation du certificat pour HAProxy

HAProxy attend un fichier unique combinant le certificat complet et la
cle privee :

```bash
sudo cat /etc/letsencrypt/live/aiops-sentinel.duckdns.org/fullchain.pem \
         /etc/letsencrypt/live/aiops-sentinel.duckdns.org/privkey.pem \
         | sudo tee /etc/letsencrypt/live/aiops-sentinel.duckdns.org/haproxy.pem
```

### Configuration HAProxy pour le HTTPS

`infra/k8s-oracle/haproxy/haproxy.cfg` (ajout par rapport a la
configuration de base) :
```text
frontend http_front
    bind *:80
    bind *:443 ssl crt /usr/local/etc/haproxy/certs/haproxy.pem
    acl is_llm path_beg /llm
    use_backend llama_server_back if is_llm
    default_backend api_gateway_back
```

`infra/k8s-oracle/haproxy/deployment.yaml` (ajouts) :
```yaml
          ports:
            - containerPort: 80
              hostPort: 80
            - containerPort: 443
              hostPort: 443
          volumeMounts:
            - name: haproxy-config-volume
              mountPath: /usr/local/etc/haproxy/haproxy.cfg
              subPath: haproxy.cfg
            - name: tls-cert-volume
              mountPath: /usr/local/etc/haproxy/certs
              readOnly: true
      volumes:
        - name: haproxy-config-volume
          configMap:
            name: haproxy-config
        - name: tls-cert-volume
          hostPath:
            path: /etc/letsencrypt/live/aiops-sentinel.duckdns.org
            type: Directory
```

### Ouverture du port 443

```bash
sudo firewall-cmd --permanent --add-port=443/tcp
sudo firewall-cmd --reload
```

Ainsi qu'une regle d'entree correspondante dans la Security List
Oracle (port 443, TCP, source 0.0.0.0/0).

### Application et redemarrage

```bash
cd ~/aiops-sentinel

kubectl create configmap haproxy-config \
  --namespace=aiops-sentinel \
  --from-file=infra/k8s-oracle/haproxy/haproxy.cfg \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl apply -f infra/k8s-oracle/haproxy/deployment.yaml
kubectl scale deployment haproxy -n aiops-sentinel --replicas=1
```

### Verification finale

Depuis un poste externe, en HTTPS :
```bash
curl -s https://aiops-sentinel.duckdns.org/
```
```text
{"status":"ok","service":"AIOps Sentinel API"}
```

```bash
curl -s https://aiops-sentinel.duckdns.org/docs -o /dev/null -w "%{http_code}\n"
```
```text
200
```

```bash
curl -s https://aiops-sentinel.duckdns.org/llm/health
```
```text
{"status":"ok"}
```

## 3. Resultat

L'architecture est accessible en HTTPS via un nom de domaine stable,
avec un certificat valide reconnu par les navigateurs. Le
renouvellement du certificat est pris en charge automatiquement par
Certbot.

## 4. Points de reference

| Element | Valeur |
|---|---|
| Nom de domaine | aiops-sentinel.duckdns.org |
| Certificat | Let's Encrypt, expiration 2026-12-19, renouvellement automatique |
| Point d'entree HTTPS | https://aiops-sentinel.duckdns.org/ |
| Documentation Swagger | https://aiops-sentinel.duckdns.org/docs |
| Interface LLM local | https://aiops-sentinel.duckdns.org/llm/ |
