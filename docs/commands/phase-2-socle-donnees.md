# Phase 2 — Socle de donnees

## 1. Comprendre cette phase

### Besoin

Le projet a besoin de deux types de stockage et d'un environnement de
collecte, avant que les agents IA puissent fonctionner :

- Un endroit ou stocker l'inventaire de l'infrastructure (serveurs,
  services, incidents) sous forme de tables : c'est PostgreSQL.
- Un endroit ou stocker de la documentation technique sous forme de
  vecteurs, pour permettre une recherche par sens plutot que par mot-cle
  exact : c'est Qdrant.
- Un environnement isole pour collecter cette documentation depuis le web,
  sans polluer le poste de travail principal : c'est la VM Vagrant.

Cette phase ne construit encore aucun agent IA ; elle prepare uniquement
le terrain sur lequel les phases suivantes vont s'appuyer.

### Architecture

```text
Poste de travail (RHEL 9)
  |
  +-- Conteneurs Podman
  |     +-- PostgreSQL (port 5432) : inventaire structure
  |     +-- Qdrant (port 6333)     : base vectorielle
  |
  +-- VM Vagrant/libvirt (192.168.121.0/24)
        +-- Crawl4AI : collecte de documentation web
```

La VM et les conteneurs de l'hote communiquent via le reseau prive cree
par libvirt. Ce reseau est bloque par defaut par le pare-feu du poste de
travail ; une regle explicite est necessaire pour autoriser la VM a
joindre les services de l'hote (Qdrant notamment, utilise en Phase 4).

### Les fichiers de cette phase et leur role

**`infra/compose/docker-compose.yml`**
Decrit les deux conteneurs (PostgreSQL et Qdrant) : image utilisee, ports
exposes, volumes de persistance, et verification de sante (healthcheck).
C'est ce fichier que `podman-compose` lit pour savoir quoi demarrer.

**`infra/compose/.env`** (non versionne) et **`.env.example`** (versionne)
Contiennent les identifiants PostgreSQL. Le fichier `.env` reel n'est
jamais publie ; `.env.example` documente la forme attendue avec des
valeurs factices.

**`db/schema.sql`**
Definit la structure de l'inventaire : trois tables, `servers` (machines),
`services` (ce qui tourne sur les machines), `incidents` (problemes
rencontres). Une table `services` reference toujours un `server_id` ; une
table `incidents` peut referencer un serveur et/ou un service concerne.

**`db/seed.sql`**
Insere des donnees de demonstration dans ces trois tables, pour que les
agents des phases suivantes aient une matiere reelle a interroger.

**`db/create_readonly_user.sql`**
Cree un second utilisateur PostgreSQL, `infra_readonly`, dote uniquement
de droits de lecture (`SELECT`). Cet utilisateur est celui que l'agent
SQL (Phase 3) utilisera pour executer les requetes generees par le
modele de langage, de sorte qu'aucune requete de modification ou de
suppression ne puisse aboutir, meme en cas d'erreur de generation.

**`crawler/Vagrantfile`**
Definit la machine virtuelle utilisee pour la collecte de documentation :
image Rocky Linux 9, ressources allouees (2 Go de RAM, 2 CPU), adresse IP
fixe sur le reseau prive. Cette VM est deliberement separee du poste de
travail principal, afin que l'installation d'un navigateur headless et
de ses dependances (necessaire a Crawl4AI, voir Phase 4) reste isolee.

## 2. Commandes utilisees

### Initialisation du depot Git

```bash
git init
git branch -m main
git remote add origin git@github.com:Med-ABDELGHANI/aiops-sentinel.git
```

### Provisionnement PostgreSQL et Qdrant

```bash
openssl rand -base64 24
```
```bash
cd infra/compose
podman-compose up -d
podman-compose ps
```
```bash
podman inspect <nom_conteneur> --format '{{json .State.Health}}' | python3 -m json.tool
```

### Initialisation du schema PostgreSQL

```bash
podman exec -i aiops-postgres psql -U aiops -d aiops_sentinel < db/schema.sql
podman exec -i aiops-postgres psql -U aiops -d aiops_sentinel < db/seed.sql
podman exec -i aiops-postgres psql -U aiops -d aiops_sentinel < db/create_readonly_user.sql
```

Verification :
```bash
podman exec -it aiops-postgres psql -U aiops -d aiops_sentinel -c "\dt"
```

### Provisionnement de la VM de collecte

```bash
sudo dnf install -y qemu-kvm libvirt libvirt-devel virt-install virt-manager
sudo systemctl enable --now libvirtd
sudo usermod -aG libvirt $(whoami)
newgrp libvirt
```
```bash
sudo dnf install -y vagrant
vagrant plugin install vagrant-libvirt
```
```bash
cd crawler
vagrant up --provider=libvirt
vagrant ssh
```

### Installation de Crawl4AI sur la VM

```bash
sudo dnf install -y python3.11 python3.11-pip git
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

mkdir -p ~/crawler-app && cd ~/crawler-app
uv venv --python 3.11
source .venv/bin/activate
uv pip install crawl4ai
crawl4ai-setup
```
```bash
sudo dnf install -y \
  nss nspr atk at-spi2-atk cups-libs libdrm libxkbcommon \
  libXcomposite libXdamage libXext libXfixes libXrandr \
  mesa-libgbm alsa-lib pango cairo
python3 -m playwright install chromium
```

### Ouverture du pare-feu (acces VM vers services de l'hote)

```bash
sudo firewall-cmd --zone=libvirt --add-rich-rule='rule family="ipv4" source address="192.168.121.0/24" port protocol="tcp" port="6333" accept' --permanent
sudo firewall-cmd --reload
```
