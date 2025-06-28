#!/usr/bin/env python3
import os
import zipfile
from dotenv import load_dotenv
from lightningviewer.blitz_query import requete_impacts
from pandas import DataFrame
from datetime import datetime
import subprocess

def _ensure_utc_offset(ts: str) -> str:
    """
    Ajoute « +00:00 » à une chaîne ISO si aucun décalage n'est présent.
    Permet d'accepter 2025-06-01T18:00 et 2025-06-01T18:00+00:00.
    """
    if "Z" in ts or "+" in ts or "-" in ts[11:]:
        return ts  # possède déjà un indicateur
    return ts + "+00:00"

def build_kmz(df: DataFrame,
              output_path: str,
              center_lat: float,
              center_lon: float,
              rayon_km: float,
              nom: str = "impacts"):
    """
    Construit un fichier KMZ à partir d’un DataFrame contenant des colonnes :
    - timestamp
    - lat
    - lon
    - mcg  (max circular gap : précision des stations)
    """
    kml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<kml xmlns="http://www.opengis.net/kml/2.2">',
        f'''  <Document><name>{nom}</name>
         <Style id="red"><IconStyle><color>ff0000ff</color><scale>0.8</scale>
           <Icon><href>http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png</href></Icon>
         </IconStyle></Style>
         <Style id="orange"><IconStyle><color>ff0088ff</color><scale>0.8</scale>
           <Icon><href>http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png</href></Icon>
         </IconStyle></Style>
         <Style id="yellow"><IconStyle><color>ff00ffff</color><scale>0.8</scale>
           <Icon><href>http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png</href></Icon>
         </IconStyle></Style>
         <Style id="grey"><IconStyle><color>ffaaaaaa</color><scale>0.6</scale>
           <Icon><href>http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png</href></Icon>
         </IconStyle></Style>
        <Style id="center"><IconStyle>
          <color>ff00ffff</color>          <!-- magenta/violet fluo (opaque) -->
          <scale>1.6</scale>               <!-- légèrement plus grande -->
          <Icon>
            <href>https://maps.google.com/mapfiles/kml/pushpin/purple-pushpin.png</href>
          </Icon>
        </IconStyle></Style>
         <LookAt>
           <longitude>{center_lon}</longitude>
           <latitude>{center_lat}</latitude>
           <range>{rayon_km * 20}</range>
           <tilt>0</tilt><heading>0</heading>
         </LookAt>'''
    ]

    # Repère central flashy
    center_placemark = f"""
    <Placemark>
        <styleUrl>#center</styleUrl>
        <Point><coordinates>{center_lon},{center_lat},0</coordinates></Point>
    </Placemark>
    """
    kml_lines.append(center_placemark.strip())

    for _, row in df.iterrows():
        ts = row["timestamp"]
        lat = row["lat"]
        lon = row["lon"]
        mcg = row.get("mcg")

        style = "#grey"   # par défaut pour mcg manquant
        # Estimation de précision en fonction de mcg
        if mcg is None:
            precision_txt = "précision inconnue (≈ 2‑6 km)"
        else:
            if mcg <= 120:
                style = "#red"
                precision_txt = "précision \u2264 1 km"
            elif mcg <= 240:
                style = "#orange"
                precision_txt = "précision \u2248 1‑3 km"
            else:
                style = "#yellow"
                precision_txt = "précision > 3 km"

        placemark = f"""
        <Placemark>
            <styleUrl>{style}</styleUrl>
            <TimeStamp><when>{ts}</when></TimeStamp>
            <description>{precision_txt} (mcg = {mcg})</description>
            <Point><coordinates>{lon},{lat},0</coordinates></Point>
        </Placemark>
        """
        kml_lines.append(placemark.strip())

    kml_lines.append("  </Document></kml>")

    kml_content = "\n".join(kml_lines)

    # Écriture du KML temporaire
    kml_path = output_path.replace(".kmz", ".kml")
    with open(kml_path, "w", encoding="utf-8") as f:
        f.write(kml_content)

    # Création du fichier KMZ (zip du .kml)
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as kmz:
        kmz.write(kml_path, arcname="doc.kml")

    os.remove(kml_path)
    print(f"✅ Fichier KMZ généré : {output_path}")

# ------------------------------------------------------------------
# Script de test : récupération d'impacts et génération automatique
# d'un fichier KMZ.  Lance seulement si ce fichier est exécuté
# directement (pas importé).
# ------------------------------------------------------------------
if __name__ == "__main__":
    load_dotenv()  # charge les variables d'environnement éventuelles

    # --- Période de test (doit correspondre aux données présentes) ---
    start_iso = "2025-06-01T18:00+00:00"
    end_iso   = "2025-06-01T19:00+00:00"

    # --- Paramètres du filtre spatial (centre ≈ Paris) ---
    center_lat = 38.0        # latitude médiane ≈ (12 + 65)/2
    center_lon = -28.0       # longitude médiane ≈ (-112 + 57)/2
    rayons_km  = [10000]      # large rayon pour “tout voir”
    print("🔍 Tests avec conversion automatique en UTC (+00:00) ...")

    start_dt = datetime.fromisoformat(_ensure_utc_offset(start_iso))
    end_dt   = datetime.fromisoformat(_ensure_utc_offset(end_iso))
 

    for r in rayons_km:
        print(f"\n🔍 Requête – rayon {r} km ...")

        df = requete_impacts(start_dt, end_dt,
                             center_lat=center_lat,
                             center_lon=center_lon,
                             rayon_km=r)

        print(f"✅ Données récupérées : {len(df)} lignes")
        if df.empty:
            print(f"❌ Aucun impact détecté pour r = {r} km, on passe.")
            continue

        # Chemin de sortie KMZ suffixé par le rayon
        kmz_name = f"impacts_{r}km.kmz"
        kmz_path = os.path.join(os.path.dirname(__file__), "..", kmz_name)

        build_kmz(df, kmz_path, center_lat, center_lon, r)
        print(f"📦 KMZ généré : {os.path.abspath(kmz_path)}")
        subprocess.run(["open", kmz_path])