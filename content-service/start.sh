#!/bin/bash
set -e

echo "🚀 Démarrage du Content Service avec Dapr..."

# 1. Démarrer Dapr sidecar
echo "🔧 Démarrage du sidecar Dapr..."
daprd \
  --app-id content-service \
  --app-port 8001 \
  --dapr-http-port 3500 \
  --dapr-grpc-port 50001 \
  --components-path /app/dapr/components \
  --log-level info &

# 2. Attendre que Dapr soit prêt
echo "⏳ Attente que Dapr soit prêt..."
sleep 5

# 3. Vérifier que Dapr est en cours d'exécution
echo "✅ Dapr démarré, vérification..."
if pgrep -x "daprd" > /dev/null; then
    echo "🎯 Dapr est en cours d'exécution"
else
    echo "❌ Dapr n'est pas en cours d'exécution"
    exit 1
fi

# 4. Démarrer l'application Python
echo "🐍 Démarrage de l'application Python..."
exec python app.py