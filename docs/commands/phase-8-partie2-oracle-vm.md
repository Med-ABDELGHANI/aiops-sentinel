# Phase 8 (partie 2) — Creation et configuration de la VM Oracle Cloud

## 1. Comprendre cette phase

### Besoin

Heberger l'architecture AIOps Sentinel sur une infrastructure cloud
publique, accessible en permanence depuis Internet, en remplacement du
deploiement local (PC personnel).

### Choix du fournisseur

Oracle Cloud Infrastructure (OCI) a ete retenu pour son offre Always Free :
une instance de calcul Ampere (architecture ARM), avec 4 OCPU et 24 Go de
RAM, gratuite de facon permanente (sans limite de duree), ainsi qu'un
volume de stockage bloc de 200 Go inclus.

### Architecture de l'instance

| Parametre | Valeur |
|---|---|
| Nom de l'instance | aiops-sentinel-prod |
| Shape | VM.Standard.A1.Flex (Ampere, ARM) |
| Ressources | 4 OCPU / 24 Go RAM |
| Systeme d'exploitation | Oracle Linux 9.8 |
| Region | France Central (Paris) |
| Reseau | VCN dedie avec sous-reseau public |
| Adresse IP publique | Ephemere, attachee manuellement |

## 2. Commandes utilisees

### Creation de l'instance

Console Oracle Cloud : Compute > Instances > Create Instance, avec :
- Image : Oracle Linux 9
- Forme : Ampere > VM.Standard.A1.Flex, 4 OCPU / 24 Go
- Reseau : creation d'un nouveau VCN et sous-reseau public
- Cle SSH : generation d'une nouvelle paire de cles, telechargement de
  la cle privee

### Configuration de l'adresse IP publique

L'attribution automatique d'IP publique n'etant pas disponible lors de
la creation inline du sous-reseau, l'action rapide "Connecter le
sous-reseau public a Internet" a ete utilisee pour configurer la
passerelle Internet et le groupe de securite reseau, puis une adresse
IP publique ephemere a ete attachee manuellement a l'adresse IP privee
principale de la VNIC (Fonctions de reseau > VNIC > Administration
d'adresse IP > Modifier > Adresse IP publique ephemere).

Adresse IP publique obtenue : `141.145.215.142`

### Securisation de la cle SSH

```bash
mkdir -p ~/.ssh
mv ~/Telechargements/ssh-key-*.key ~/.ssh/oracle-aiops-sentinel.key
chmod 600 ~/.ssh/oracle-aiops-sentinel.key
```

### Connexion SSH

```bash
ssh -i ~/.ssh/oracle-aiops-sentinel.key opc@141.145.215.142
```

### Verification des ressources de l'instance

```bash
cat /etc/os-release
nproc
free -h
df -h
```

Resultat :
```text
NAME="Oracle Linux Server"
VERSION="9.8"

nproc: 4

               total        used        free      shared  buff/cache   available
Mem:            22Gi       667Mi        21Gi        13Mi       784Mi        21Gi
Swap:          5.0Gi          0B       5.0Gi

Filesystem                  Size  Used Avail Use% Mounted on
/dev/mapper/ocivolume-root   30G  9.5G   20G  33% /
```

## 3. Ouverture des ports reseau (Security List)

L'acces externe a l'instance necessite l'ouverture explicite de chaque
port utilise, a deux niveaux distincts :

1. Le firewall interne de la VM (firewalld)
2. La liste de securite (Security List) du sous-reseau, au niveau du
   VCN Oracle

### Firewall interne (firewalld)

```bash
sudo firewall-cmd --permanent --add-port=30080/tcp
sudo firewall-cmd --permanent --add-port=80/tcp
sudo firewall-cmd --permanent --add-port=443/tcp
sudo firewall-cmd --reload
sudo firewall-cmd --list-ports
```

Resultat :
```text
80/tcp 443/tcp 30080/tcp
```

### Security List Oracle

Console Oracle Cloud : Instance > Fonctions de reseau > Sous-reseau >
Securite > Default Security List > Regles d'entree > Ajouter des
regles d'entree, pour chacun des ports suivants :

| Port | Protocole | Source | Usage |
|---|---|---|---|
| 22 | TCP | 0.0.0.0/0 | SSH (deja present par defaut) |
| 30080 | TCP | 0.0.0.0/0 | HAProxy (NodePort) |
| 80 | TCP | 0.0.0.0/0 | HTTP / validation Let's Encrypt |
| 443 | TCP | 0.0.0.0/0 | HTTPS |

## 4. Resultat

Instance operationnelle, accessible en SSH, avec les ports necessaires
ouverts a deux niveaux (firewall systeme et reseau cloud Oracle). Base
prete pour l'installation des outils applicatifs (partie 3).

## 5. Informations de reference

| Element | Valeur |
|---|---|
| Nom de l'instance | aiops-sentinel-prod |
| Adresse IP publique | 141.145.215.142 |
| Utilisateur SSH | opc |
| Cle privee | ~/.ssh/oracle-aiops-sentinel.key |
| OS | Oracle Linux 9.8 |
| Ressources | 4 OCPU / 24 Go RAM |
