# Image de base : Python 3.11 en version allegee (slim), deja installee
FROM python:3.11-slim

# Dossier de travail a l'interieur du conteneur - toutes les commandes
# suivantes s'executent depuis ce dossier
WORKDIR /app

# Copie d'abord uniquement le fichier des dependances (pas encore le code)
# pour beneficier de la mise en cache : si le code change mais pas les
# dependances, cette etape n'est pas refaite lors d'une reconstruction
COPY requirements.txt .

# Installe les dependances listees dans requirements.txt
# --no-cache-dir evite de garder les fichiers temporaires de pip, image plus legere
RUN pip install --no-cache-dir -r requirements.txt

# Copie maintenant le vrai code de l'API (tout le dossier app/, avec ses
# sous-dossiers routers/, ses fichiers models.py, schemas.py, etc.)
COPY app/ ./app/
#COPY  /home/mohamed/aiops-sentinel/api/app/   /app/app/ 

# Documente (a titre informatif) que ce conteneur ecoute sur le port 8000
EXPOSE 8000

# Commande executee automatiquement au demarrage du conteneur :
# lance le serveur Uvicorn, qui sert l'application FastAPI (app.main:app),
# accessible depuis n'importe quelle interface reseau (0.0.0.0), port 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
