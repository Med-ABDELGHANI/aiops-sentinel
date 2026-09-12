# Phase 2 — Socle de donnees

## Objectif

Mettre en place l'infrastructure de donnees du projet : depot Git, bases
PostgreSQL et Qdrant conteneurisees, et une machine virtuelle dediee a la
collecte de documentation via Crawl4AI.

## Architecture

```text
Depot Git (GitHub)
Conteneurs Podman : PostgreSQL (inventaire) + Qdrant (vecteurs)
VM Vagrant/libvirt : Rocky Linux 9, Crawl4AI
```

La VM communique avec les conteneurs de l'hote via le reseau prive
192.168.121.0/24 (interface virbr0, zone firewalld "libvirt").

## Prerequis

- RHEL 9, utilisateur non privilegie avec acces sudo
- Podman et podman-compose installes
- Compte GitHub avec cle SSH configuree

## Procedure

### 1. Initialisation du depot Git

```bash
git init
git branch -m main
git remote add origin git@github.com:Med-ABDELGHANI/aiops-sentinel.git
```

En cas de commit initial avec une identite auto-generee :

```bash
git config --global user.name "Nom Prenom"
git config --global user.email "email@exemple.com"
git commit --amend --reset-author --no-edit
git push --force-with-lease
```

### 2. Provisionnement PostgreSQL et Qdrant

Mot de passe fort pour l'utilisateur PostgreSQL principal :

```bash
openssl rand -base64 24
```

Demarrage des services :

```bash
cd infra/compose
podman-compose up -d
podman-compose ps
```

Verification de l'etat de sante d'un conteneur :

```bash
podman inspect <nom_conteneur> --format '{{json .State.Health}}' | python3 -m json.tool
```

### 3. Initialisation du schema PostgreSQL

```bash
podman exec -i aiops-postgres psql -U aiops -d aiops_sentinel < db/schema.sql
podman exec -i aiops-postgres psql -U aiops -d aiops_sentinel < db/seed.sql
```

Verification :

```bash
podman exec -it aiops-postgres psql -U aiops -d aiops_sentinel -c "\dt"
```

### 4. Provisionnement de la VM de collecte (Crawl4AI)

Dependances systeme (KVM/QEMU/libvirt) :

```bash
sudo dnf install -y qemu-kvm libvirt libvirt-devel virt-install virt-manager
sudo systemctl enable --now libvirtd
sudo usermod -aG libvirt $(whoami)
newgrp libvirt
```

Verification de l'acces libvirt :

```bash
groups
virsh -c qemu:///system list --all
```

Installation de Vagrant et du plugin libvirt :

```bash
sudo dnf install -y vagrant
vagrant plugin install vagrant-libvirt
vagrant plugin list
```

Demarrage de la VM (definie dans `crawler/Vagrantfile`) :

```bash
cd crawler
vagrant up --provider=libvirt
vagrant ssh
```

### 5. Installation de Crawl4AI sur la VM

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

Rocky Linux n'etant pas officiellement supporte par Playwright, les
dependances navigateur doivent etre installees manuellement :

```bash
sudo dnf install -y \
  nss nspr atk at-spi2-atk cups-libs libdrm libxkbcommon \
  libXcomposite libXdamage libXext libXfixes libXrandr \
  mesa-libgbm alsa-lib pango cairo
python3 -m playwright install chromium
```

### 6. Ouverture du pare-feu (acces VM vers services de l'hote)

Le reseau de la VM (192.168.121.0/24) appartient a la zone firewalld
`libvirt`, distincte de la zone `public` associee a l'interface reseau
principale. Autorisation d'acces a Qdrant (port 6333) :

```bash
sudo firewall-cmd --zone=libvirt --add-rich-rule='rule family="ipv4" source address="192.168.121.0/24" port protocol="tcp" port="6333" accept' --permanent
sudo firewall-cmd --reload
```

## Configuration

Fichier `infra/compose/.env` (non versionne), a partir de `.env.example` :

```bash
POSTGRES_USER=aiops
POSTGRES_PASSWORD=<mot de passe genere>
POSTGRES_DB=aiops_sentinel
INFRA_READONLY_PASSWORD=<mot de passe genere>
```

## Verification

Test fonctionnel de Crawl4AI sur la VM :

```python
import asyncio
from crawl4ai import AsyncWebCrawler

async def main():
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url="https://example.com")
        print("Titre trouve :", result.metadata.get("title"))
        print("Longueur du markdown extrait :", len(result.markdown))

asyncio.run(main())
```

Sante de Qdrant, depuis la VM ou l'hote :

```bash
curl -s http://localhost:6333/healthz
```

## Depannage

**`sshd` en boucle de redemarrage sur la VM (`OpenSSL version mismatch`)**

Cause : une mise a jour automatique du systeme a mis a jour OpenSSL sans
recompiler le paquet `openssh-server` en consequence.

Correction :

```bash
sudo dnf update -y openssh-server openssh
sudo systemctl restart sshd
```

**Connexion refusee depuis la VM vers un service de l'hote**

Cause : trafic bloque par firewalld, zone `libvirt` non autorisee par
defaut pour le port concerne (voir procedure, etape 6).
