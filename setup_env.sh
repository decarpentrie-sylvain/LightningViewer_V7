#!/bin/bash

# === Script d’installation environnement virtuel pour LightningViewer_V7 ===

# Se placer dans le dossier du script
cd "$(dirname "$0")"

echo "🔧 Création de l'environnement virtuel (.venv)..."
python3 -m venv .venv

echo "✅ Environnement créé."

echo "🚀 Activation de l’environnement..."
source .venv/bin/activate

echo "📦 Installation des dépendances..."
pip install --upgrade pip
pip install python-dotenv requests tqdm

# Crée un fichier .env de base s’il n’existe pas déjà
if [ ! -f .env ]; then
  echo "BLITZ_LOGIN=" >> .env
  echo "BLITZ_PASSWORD=" >> .env
  echo "✅ Fichier .env créé (à remplir)."
else
  echo "ℹ️ Fichier .env déjà présent — non modifié."
fi

echo "✅ Tout est prêt !"
echo "➡️ Pour activer l’environnement à chaque session :"
echo "   source .venv/bin/activate"