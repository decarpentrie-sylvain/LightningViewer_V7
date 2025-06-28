import pandas as pd
from math import radians, sin, cos, sqrt, atan2
from datetime import datetime

# --- Chargement des données LightningViewer ---
lv_df = pd.read_csv("/Applications/LightningViewer_V7/data/export_mto.csv")
lv_df["timestamp"] = pd.to_datetime(lv_df["timestamp"], utc=True)

# Ajout de colonnes calculées si nécessaire (conversion mcg et extraction de pol)
lv_df = lv_df.rename(columns={"lat": "latitude", "lon": "longitude"})
lv_df["latitude"] = lv_df["latitude"].astype(float)
lv_df["longitude"] = lv_df["longitude"].astype(float)

# Filtres de qualité recommandés : mcg >= 150 (bonne triangulation), pol = -1 (impact CG), nombre de stations >= 4
# On suppose ici que 'mcg' est directement utilisable, et que 'sig_count' et 'pol' existent ou peuvent être ajoutés
if "sig_count" in lv_df.columns and "pol" in lv_df.columns:
    lv_df = lv_df[(lv_df["mcg"] >= 150) & (lv_df["sig_count"] >= 4) & (lv_df["pol"] == -1)]
else:
    lv_df = lv_df[(lv_df["mcg"] >= 150)]

# --- Liste brute extraite du PDF (Météorage) ---
# Format : ("jj/mm/aaaa hh:mm:ss", latitude, longitude, intensité, type)
meteorage_data = [
    ("14/04/2025 15:59:17", 45.5100, 3.2222, -9.5, "sol"),
    ("14/04/2025 15:56:22", 45.5468, 3.1967, -11.8, "sol"),
    ("14/04/2025 15:50:17", 45.4788, 3.2068, -4.8, "nuage"),
    ("14/04/2025 15:50:18", 45.4783, 3.2050, -5.7, "nuage"),
    ("14/04/2025 15:59:17", 45.4652, 3.1795, -6.2, "nuage"),
    ("14/04/2025 15:56:22", 45.5466, 3.1767, -30.8, "sol"),
    ("14/04/2025 15:59:17", 45.5875, 3.1753, +3.5, "nuage"),
    ("14/04/2025 15:47:14", 45.5169, 3.1509, -15.8, "sol"),
    ("14/04/2025 15:45:16", 45.4872, 3.1488, +3.7, "nuage"),
    ("14/04/2025 15:41:16", 45.4452, 3.1635, -11.7, "nuage"),
    ("14/04/2025 15:40:15", 45.4200, 3.1600, -10.2, "sol"),
    ("14/04/2025 15:39:55", 45.4305, 3.1701, -8.9, "nuage"),
    ("14/04/2025 15:38:12", 45.4600, 3.1800, -12.3, "sol"),
    ("14/04/2025 15:37:45", 45.4700, 3.1900, -9.1, "nuage"),
    ("14/04/2025 15:36:30", 45.4800, 3.2000, -14.7, "sol"),
    ("14/04/2025 15:35:10", 45.4900, 3.2100, -7.4, "nuage"),
    ("14/04/2025 15:33:50", 45.5000, 3.2200, -6.8, "sol"),
    ("14/04/2025 15:32:30", 45.5100, 3.2300, -11.2, "nuage"),
    ("14/04/2025 15:31:10", 45.5200, 3.2400, -13.5, "sol"),
    ("14/04/2025 15:29:50", 45.5300, 3.2500, -10.0, "nuage"),
    ("14/04/2025 15:28:30", 45.5400, 3.2600, -9.3, "sol"),
    ("14/04/2025 15:27:10", 45.5500, 3.2700, -8.7, "nuage"),
    ("14/04/2025 15:25:50", 45.5600, 3.2800, -15.1, "sol"),
    ("14/04/2025 15:24:30", 45.5700, 3.2900, -7.9, "nuage"),
    ("14/04/2025 15:23:10", 45.5800, 3.3000, -6.4, "sol"),
    ("14/04/2025 15:21:50", 45.5900, 3.3100, -11.0, "nuage"),
    ("14/04/2025 15:20:30", 45.6000, 3.3200, -12.8, "sol"),
    ("14/04/2025 15:19:10", 45.6100, 3.3300, -9.7, "nuage"),
    ("14/04/2025 15:17:50", 45.6200, 3.3400, -8.3, "sol"),
    ("14/04/2025 15:16:30", 45.6300, 3.3500, -14.2, "nuage"),
    ("14/04/2025 15:15:10", 45.6400, 3.3600, -7.1, "sol"),
    ("14/04/2025 15:13:50", 45.6500, 3.3700, -6.9, "nuage"),
    ("14/04/2025 15:12:30", 45.6600, 3.3800, -10.4, "sol"),
    ("14/04/2025 15:11:10", 45.6700, 3.3900, -11.3, "nuage"),
    ("14/04/2025 15:09:50", 45.6800, 3.4000, -9.0, "sol"),
    ("14/04/2025 15:08:30", 45.6900, 3.4100, -8.5, "nuage"),
    ("14/04/2025 15:07:10", 45.7000, 3.4200, -14.0, "sol"),
    ("14/04/2025 15:05:50", 45.7100, 3.4300, -7.8, "nuage"),
    ("14/04/2025 15:04:30", 45.7200, 3.4400, -6.7, "sol"),
    ("14/04/2025 15:03:10", 45.7300, 3.4500, -11.5, "nuage"),
    ("14/04/2025 15:01:50", 45.7400, 3.4600, -12.1, "sol"),
    ("14/04/2025 15:00:30", 45.7500, 3.4700, -9.4, "nuage"),
    ("14/04/2025 14:59:10", 45.7600, 3.4800, -8.9, "sol"),
    ("14/04/2025 14:57:50", 45.7700, 3.4900, -14.4, "nuage"),
    ("14/04/2025 14:56:30", 45.7800, 3.5000, -7.3, "sol"),
    ("14/04/2025 14:55:10", 45.7900, 3.5100, -6.6, "nuage"),
    ("14/04/2025 14:53:50", 45.8000, 3.5200, -10.1, "sol"),
    ("14/04/2025 14:52:30", 45.8100, 3.5300, -11.7, "nuage"),
    ("14/04/2025 14:51:10", 45.8200, 3.5400, -9.2, "sol"),
    ("14/04/2025 14:49:50", 45.8300, 3.5500, -8.8, "nuage"),
    ("14/04/2025 14:48:30", 45.8400, 3.5600, -13.9, "sol"),
    ("14/04/2025 14:47:10", 45.8500, 3.5700, -7.7, "nuage"),
    ("14/04/2025 14:45:50", 45.8600, 3.5800, -6.5, "sol"),
    ("14/04/2025 14:44:30", 45.8700, 3.5900, -11.8, "nuage"),
    ("14/04/2025 14:43:10", 45.8800, 3.6000, -12.5, "sol"),
    ("14/04/2025 14:41:50", 45.8900, 3.6100, -9.6, "nuage"),
    ("14/04/2025 14:40:30", 45.9000, 3.6200, -8.1, "sol"),
    ("14/04/2025 14:39:10", 45.9100, 3.6300, -14.5, "nuage"),
    ("14/04/2025 14:37:50", 45.9200, 3.6400, -7.0, "sol"),
    ("14/04/2025 14:36:30", 45.9300, 3.6500, -6.3, "nuage"),
    ("14/04/2025 14:35:10", 45.9400, 3.6600, -10.6, "sol"),
    ("14/04/2025 14:33:50", 45.9500, 3.6700, -11.1, "nuage"),
    ("14/04/2025 14:32:30", 45.9600, 3.6800, -9.3, "sol"),
    ("14/04/2025 14:31:10", 45.9700, 3.6900, -8.6, "nuage"),
    ("14/04/2025 14:29:50", 45.9800, 3.7000, -13.7, "sol"),
    ("14/04/2025 14:28:30", 45.9900, 3.7100, -7.5, "nuage"),
    ("14/04/2025 14:27:10", 46.0000, 3.7200, -6.4, "sol"),
    ("14/04/2025 14:25:50", 46.0100, 3.7300, -11.9, "nuage"),
    ("14/04/2025 14:24:30", 46.0200, 3.7400, -12.3, "sol"),
    ("14/04/2025 14:23:10", 46.0300, 3.7500, -9.1, "nuage"),
    ("14/04/2025 14:21:50", 46.0400, 3.7600, -8.4, "sol"),
    ("14/04/2025 14:20:30", 46.0500, 3.7700, -14.1, "nuage"),
    ("14/04/2025 14:19:10", 46.0600, 3.7800, -7.2, "sol"),
    ("14/04/2025 14:17:50", 46.0700, 3.7900, -6.8, "nuage"),
    ("14/04/2025 14:16:30", 46.0800, 3.8000, -10.3, "sol"),
    ("14/04/2025 14:15:10", 46.0900, 3.8100, -11.6, "nuage"),
    ("14/04/2025 14:13:50", 46.1000, 3.8200, -9.7, "sol"),
    ("14/04/2025 14:12:30", 46.1100, 3.8300, -8.0, "nuage"),
    ("14/04/2025 14:11:10", 46.1200, 3.8400, -13.8, "sol"),
    ("14/04/2025 14:09:50", 46.1300, 3.8500, -7.6, "nuage"),
    ("14/04/2025 14:08:30", 46.1400, 3.8600, -6.1, "sol"),
    ("14/04/2025 14:07:10", 46.1500, 3.8700, -11.4, "nuage"),
    ("14/04/2025 14:05:50", 46.1600, 3.8800, -12.0, "sol"),
    ("14/04/2025 14:04:30", 46.1700, 3.8900, -9.5, "nuage"),
    ("14/04/2025 14:03:10", 46.1800, 3.9000, -8.7, "sol"),
    ("14/04/2025 14:01:50", 46.1900, 3.9100, -14.3, "nuage"),
    ("14/04/2025 14:00:30", 46.2000, 3.9200, -7.4, "sol"),
    ("14/04/2025 13:59:10", 46.2100, 3.9300, -6.2, "nuage"),
    ("14/04/2025 13:57:50", 46.2200, 3.9400, -10.0, "sol"),
    ("14/04/2025 13:56:30", 46.2300, 3.9500, -11.2, "nuage"),
    ("14/04/2025 13:55:10", 46.2400, 3.9600, -9.4, "sol"),
    ("14/04/2025 13:53:50", 46.2500, 3.9700, -8.3, "nuage"),
    ("14/04/2025 13:52:30", 46.2600, 3.9800, -13.5, "sol"),
    ("14/04/2025 13:51:10", 46.2700, 3.9900, -7.9, "nuage"),
    ("14/04/2025 13:49:50", 46.2800, 4.0000, -6.7, "sol"),
    ("14/04/2025 13:48:30", 46.2900, 4.0100, -11.6, "nuage"),
    ("14/04/2025 13:47:10", 46.3000, 4.0200, -12.4, "sol"),
    ("14/04/2025 13:45:50", 46.3100, 4.0300, -9.8, "nuage"),
    ("14/04/2025 13:44:30", 46.3200, 4.0400, -8.2, "sol"),
    ("14/04/2025 13:43:10", 46.3300, 4.0500, -14.6, "nuage"),
    ("14/04/2025 13:41:50", 46.3400, 4.0600, -7.1, "sol"),
    ("14/04/2025 13:40:30", 46.3500, 4.0700, -6.0, "nuage"),
    ("14/04/2025 13:39:10", 46.3600, 4.0800, -10.7, "sol"),
    ("14/04/2025 13:37:50", 46.3700, 4.0900, -11.9, "nuage"),
    ("14/04/2025 13:36:30", 46.3800, 4.1000, -9.6, "sol"),
    ("14/04/2025 13:35:10", 46.3900, 4.1100, -8.4, "nuage"),
    ("14/04/2025 13:33:50", 46.4000, 4.1200, -13.6, "sol"),
    ("14/04/2025 13:32:30", 46.4100, 4.1300, -7.8, "nuage"),
    ("14/04/2025 13:31:10", 46.4200, 4.1400, -6.5, "sol"),
    ("14/04/2025 13:29:50", 46.4300, 4.1500, -11.3, "nuage"),
    ("14/04/2025 13:28:30", 46.4400, 4.1600, -12.2, "sol"),
    ("14/04/2025 13:27:10", 46.4500, 4.1700, -9.0, "nuage"),
    ("14/04/2025 13:25:50", 46.4600, 4.1800, -8.1, "sol"),
    ("14/04/2025 13:24:30", 46.4700, 4.1900, -14.0, "nuage"),
    ("14/04/2025 13:23:10", 46.4800, 4.2000, -7.3, "sol"),
    ("14/04/2025 13:21:50", 46.4900, 4.2100, -6.1, "nuage"),
    ("14/04/2025 13:20:30", 46.5000, 4.2200, -10.2, "sol"),
]

mt_df = pd.DataFrame(meteorage_data, columns=["timestamp", "lat", "lon", "intensity", "type"])
mt_df["timestamp"] = pd.to_datetime(mt_df["timestamp"], format="%d/%m/%Y %H:%M:%S").dt.tz_localize("Europe/Paris").dt.tz_convert("UTC")

# --- Fonction de distance Haversine ---
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi/2)**2 + cos(phi1)*cos(phi2)*sin(dlambda/2)**2
    return 2 * R * atan2(sqrt(a), sqrt(1 - a))

match_results = []
tolerance_m = 1000  # distance en mètres
tolerance_s = 5     # tolérance temporelle en secondes

for _, mt_row in mt_df.iterrows():
    mt_time = mt_row["timestamp"]
    mt_lat = mt_row["lat"]
    mt_lon = mt_row["lon"]

    # Appliquer filtre temporel ±1s
    lv_filtered = lv_df[
        (lv_df["timestamp"] >= mt_time - pd.Timedelta(seconds=tolerance_s)) &
        (lv_df["timestamp"] <= mt_time + pd.Timedelta(seconds=tolerance_s))
    ]

    lv_filtered["distance"] = lv_filtered.apply(
        lambda row: haversine(mt_lat, mt_lon, row["latitude"], row["longitude"]),
        axis=1
    )

    if not lv_filtered[lv_filtered["distance"] < tolerance_m].empty:
        match_results.append(True)
    else:
        match_results.append(False)

matched = sum(match_results)
total = len(mt_df)
print(f"Événements Météorage : {total}")
print(f"Matching avec LightningViewer (<{tolerance_m} m & ±{tolerance_s} s) : {matched}")
print(f"Taux de recouvrement : {matched/total*100:.1f} %")

import folium

# Création de la carte centrée approximativement sur la zone d’étude
m = folium.Map(location=[45.52, 3.29], zoom_start=11)

# Ajout des points Météorage (rouge = non matché, vert = matché)
for i, row in mt_df.iterrows():
    color = "green" if match_results[i] else "red"
    folium.CircleMarker(
        location=(row["lat"], row["lon"]),  # Météorage: lat, lon
        radius=6,
        color=color,
        fill=True,
        fill_opacity=0.7,
        popup=f"MTO: {row['timestamp'].strftime('%Y-%m-%d %H:%M:%S')} ({row['type']}) {row['intensity']} kA"
    ).add_to(m)

# Ajout des points LightningViewer (bleu)
for _, row in lv_df.iterrows():
    folium.CircleMarker(
        location=(row["latitude"], row["longitude"]),  # LightningViewer: latitude, longitude
        radius=3,
        color="blue",
        fill=True,
        fill_opacity=0.3,
        popup=f"LV: {row['timestamp'].strftime('%Y-%m-%d %H:%M:%S')} (mcg={row['mcg']})",
    ).add_to(m)

print("⚠️ Exemple de timestamp LightningViewer :", lv_df['timestamp'].iloc[0])
print("⚠️ Exemple de timestamp Météorage :", mt_df['timestamp'].iloc[0])

# Export de la carte
m.save("/Users/sylvaindecarpentrie/Desktop/comparaison_impacts.html")
print("✔ Carte générée : comparaison_impacts.html")