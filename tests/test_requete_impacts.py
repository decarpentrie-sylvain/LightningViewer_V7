#!/usr/bin/env python3

import logging
from datetime import datetime
from lightningviewer.blitz_query import requete_impacts

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

start = datetime(2025, 6, 1)
end = datetime(2025, 6, 24)

print("📥 Lancement de requete_impacts()...")
df = requete_impacts(start, end)
print("✅ Requête terminée")

if df.empty:
    print("⚠️ Aucun impact trouvé dans cette plage de dates.")
else:
    print("📊 Aperçu des données :")
    print(df.head())
    print(f"🔢 Nombre total de lignes : {len(df)}")