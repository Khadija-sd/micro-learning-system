# Base image Python
FROM python:3.11-slim

WORKDIR /app

# 1. Installer les outils système nécessaires
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    gnupg2 \
    procps \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 2. Installer Dapr CLI
RUN wget -q https://github.com/dapr/cli/releases/download/v1.12.0/dapr_linux_amd64.tar.gz \
    && tar -xzf dapr_linux_amd64.tar.gz \
    && mv dapr /usr/local/bin/ \
    && chmod +x /usr/local/bin/dapr \
    && rm dapr_linux_amd64.tar.gz

# 3. Installer Dapr runtime (daprd)
RUN wget -q https://github.com/dapr/dapr/releases/download/v1.12.0/daprd_linux_amd64.tar.gz \
    && tar -xzf daprd_linux_amd64.tar.gz \
    && mv daprd /usr/local/bin/ \
    && chmod +x /usr/local/bin/daprd \
    && rm daprd_linux_amd64.tar.gz

# 4. Initialiser Dapr
RUN mkdir -p /app/.dapr/components

# 5. Copier et installer les dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN python -m nltk.downloader punkt stopwords averaged_perceptron_tagger

# 6. Copier l'application
COPY . .

# 7. Créer le dossier uploads
RUN mkdir -p uploads

# 8. Exposer les ports
EXPOSE 8001 3500 50001

# 9. Script de démarrage
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

# 10. Commande par défaut
CMD ["/app/start.sh"]
