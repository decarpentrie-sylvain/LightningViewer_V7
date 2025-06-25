#!/usr/bin/env python3
import os
import requests
from dotenv import load_dotenv

# Chargement des variables d’environnement
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

if not GOOGLE_API_KEY:
    print("❌ Clé API Google manquante dans le fichier .env.")
    exit(1)

# Paramètres de la carte
center = "48.8584,2.2945"  # Tour Eiffel
zoom = 14
size = "600x400"
maptype = "roadmap"

# Construction de l’URL
url = (
    f"https://maps.googleapis.com/maps/api/staticmap?"
    f"center={center}&zoom={zoom}&size={size}&maptype={maptype}"
    f"&key={GOOGLE_API_KEY}"
)

# Téléchargement
response = requests.get(url)
if response.status_code == 200:
    with open("carte_eiffel.png", "wb") as f:
        f.write(response.content)
    print("✅ Carte enregistrée sous carte_eiffel.png")
else:
    print(f"❌ Échec ({response.status_code}) : {response.text}")