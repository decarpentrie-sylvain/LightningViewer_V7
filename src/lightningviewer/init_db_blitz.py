#!/usr/bin/env python3
from dotenv import load_dotenv
from ._paths import DATA_DIR, DB_PATH, ENV_FILE
# charger automatiquement les variables d’environnement depuis .env
load_dotenv(dotenv_path=ENV_FILE)

import sqlite3
import pathlib
import os

# Création du dossier data/ si nécessaire
DATA_DIR.mkdir(parents=True, exist_ok=True)

def main():
    # Connexion et création de la base
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()


        # Table principale des impacts (lat/lon + mcg précision)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS impacts (
            timestamp TEXT NOT NULL,
            lat REAL,
            lon REAL,
            mcg INTEGER,            -- maximal circular gap (quality/precision)
            PRIMARY KEY (timestamp, lat, lon)
        )
        """)

        # Vérifie / ajoute la colonne mcg après la création éventuelle de la table
        cur.execute("PRAGMA table_info(impacts);")
        cols = [row[1] for row in cur.fetchall()]
        if "mcg" not in cols:
            try:
                cur.execute("ALTER TABLE impacts ADD COLUMN mcg INTEGER;")
                print("ℹ️  Colonne mcg ajoutée à la table impacts")
            except sqlite3.OperationalError:
                # La colonne existe déjà (exécution concurrente)
                print("✔ Colonne mcg déjà présente (concurrent)")
        else:
            print("✔ Colonne mcg déjà présente")

        # Index spatial R-Tree
        cur.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS impacts_rtree
        USING rtree(
            id,
            min_lat, max_lat,
            min_lon, max_lon
        )
        """)
        # SQLite crée automatiquement des tables internes pour le R-Tree :
        # impacts_rtree_node, impacts_rtree_parent, impacts_rtree_rowid
        print("✅ Index spatial R-Tree créé (impacts_rtree)")

    print(f"✅ Base créée : {DB_PATH}")

def main_cli():
    main()

if __name__ == "__main__":
    main()