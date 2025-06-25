from datetime import datetime
from pprint import pprint
from blitz_query import requete_impacts

# ⏱️ Définir la période d’intérêt (UTC)
start = datetime(2024, 6, 1, 0, 0)
end = datetime(2024, 6, 1, 1, 0)

# 📍 Zone autour de Paris (optionnelle)
center_lat = 48.85
center_lon = 2.35
rayon_km = 50

# 🧪 Requête avec filtre spatial et temporel
df = requete_impacts(start, end, center_lat, center_lon, rayon_km)

print(f"✅ {len(df)} impacts récupérés dans la zone spécifiée")
pprint(df.head(10).to_dict(orient="records"))
