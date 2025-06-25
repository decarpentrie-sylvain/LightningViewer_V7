import zipfile
import os
from datetime import datetime
from pandas import DataFrame

def build_kmz(df: DataFrame, output_path: str, nom='impacts'):
    """
    Construit un fichier KMZ à partir d’un DataFrame contenant des colonnes :
    - timestamp
    - lat
    - lon
    - amplitude
    """
    kml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<kml xmlns="http://www.opengis.net/kml/2.2">',
        f'  <Document><name>{nom}</name>'
    ]

    for _, row in df.iterrows():
        ts = row["timestamp"]
        lat = row["lat"]
        lon = row["lon"]
        amp = row.get("amplitude", "N/A")

        placemark = f"""
        <Placemark>
            <TimeStamp><when>{ts}</when></TimeStamp>
            <description>Amplitude : {amp}</description>
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