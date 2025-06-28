#!/usr/bin/env python3
if __name__ == "__main__" and __package__ is None:
    import sys
    from pathlib import Path
    # Ajoute le parent de ce script (le dossier lightningviewer) au sys.path
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    # Définit le package pour que les imports relatifs fonctionnent
    __package__ = "lightningviewer"
import os
import sys
import gzip
import json
import time
import sqlite3
import logging
import pathlib
import argparse
import datetime as dt
import requests
from tqdm import tqdm
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed

# === Chargement des variables d’environnement (.env) ===
from dotenv import load_dotenv
from lightningviewer._paths import ENV_FILE
load_dotenv(dotenv_path=str(ENV_FILE))
BLITZ_LOGIN = os.getenv("BLITZ_LOGIN", "")
BLITZ_PASSWORD = os.getenv("BLITZ_PASSWORD", "")

print(f"🔍 DEBUG — BLITZ_LOGIN depuis .env : {BLITZ_LOGIN!r}")
print(f"🔍 DEBUG — BLITZ_PASSWORD défini : {'oui' if BLITZ_PASSWORD else 'non'}")

# === Constantes ===
REGION = 1
BASE_URL = "https://data.blitzortung.org/Data/Protected"
LOCAL_TZ = ZoneInfo("Europe/Paris")

from lightningviewer._paths import DB_PATH
print(f"🔍 DEBUG — DB_PATH resolved to: {DB_PATH}")

# Ensure the data directory for the SQLite database exists
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# === Fonctions ===

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Télécharge les fichiers Blitzortung 10 minutes entre deux horodatages."
    )
    parser.add_argument("start", help="Horodatage début  (YYYY-MM-DD[T]HH:MM)")
    parser.add_argument("end", help="Horodatage fin    (YYYY-MM-DD[T]HH:MM)")
    parser.add_argument("--login", help="Identifiant Blitzortung (prioritaire)")
    parser.add_argument("--password", help="Mot de passe Blitzortung (prioritaire)")
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--retry", type=int, default=3)
    parser.add_argument("--log", help="Fichier log (optionnel)")
    return parser.parse_args()

def daterange(start: dt.datetime, end: dt.datetime, step=10):
    cur = start.replace(second=0, microsecond=0, minute=(start.minute // 10) * 10)
    while cur <= end:
        yield cur
        cur += dt.timedelta(minutes=step)

def download_one(ts_utc, auth, retries=3):
    base_url = f"{BASE_URL}/Strikes_{REGION}/{ts_utc:%Y/%m/%d/%H/%M}"
    for ext in [".json", ".json.gz"]:
        for attempt in range(retries):
            url = base_url + ext
            print(f"Téléchargement : {url}")
            try:
                r = requests.get(url, auth=auth, timeout=30)
                r.raise_for_status()
                data = gzip.decompress(r.content) if ext.endswith(".gz") else r.content

                # Optionnel : sauvegarde locale brute
                archive_dir = pathlib.Path("data/archives")
                archive_dir.mkdir(parents=True, exist_ok=True)
                archive_file = archive_dir / f"{ts_utc:%Y%m%d_%H%M}.json"
                try:
                    with open(archive_file, "wb") as f:
                        f.write(data)
                except Exception as e:
                    print(f"⚠️ Échec de sauvegarde locale pour {archive_file}: {e}")

                if not data.strip():
                    print(f"⚠️ Fichier vide : {url}")
                    return False

                lignes_valides = [json.loads(l) for l in data.decode("utf-8").splitlines() if l.strip()]
                with sqlite3.connect(DB_PATH) as conn:
                    cur = conn.cursor()

                    # Insertion dans la table principale (mcg = maximal circular gap)
                    cur.executemany(
                        "INSERT OR IGNORE INTO impacts (timestamp, lat, lon, mcg) VALUES (?, ?, ?, ?)",
                        [
                            (
                                ts_utc.isoformat(),
                                ligne.get("lat"),
                                ligne.get("lon"),
                                ligne.get("mcg")          # precision / circular gap
                            )
                            for ligne in lignes_valides
                        ]
                    )

                    # Insertion dans l'index spatial R-Tree
                    for ligne in lignes_valides:
                        lat = ligne.get("lat")
                        lon = ligne.get("lon")
                        if lat is not None and lon is not None:
                            cur.execute("SELECT rowid FROM impacts WHERE timestamp = ? AND lat = ? AND lon = ?",
                                        (ts_utc.isoformat(), lat, lon))
                            row = cur.fetchone()
                            if row:
                                cur.execute("""
                                    INSERT OR IGNORE INTO impacts_rtree (id, min_lat, max_lat, min_lon, max_lon)
                                    VALUES (?, ?, ?, ?, ?)
                                """, (
                                    row[0], lat, lat, lon, lon
                                ))

                    conn.commit()

                print(f"📈 {ts_utc:%H:%M} : {len(lignes_valides)} impacts")
                return True

            except requests.RequestException:
                if attempt < retries - 1:
                    wait = 2 ** attempt
                    print(f"⚠️  Tentative {attempt+1}/{retries} échouée — nouvelle tentative dans {wait}s")
                    time.sleep(wait)
                else:
                    print(f"❌ Abandon : {url}")
    return False

def main():
    args = _parse_args()

    # Initialisation du log si précisé
    logging.basicConfig(
        filename=args.log if args.log else None,
        filemode="w",
        level=logging.INFO,
        format="%(asctime)s - %(message)s"
    )

    user = args.login or BLITZ_LOGIN
    pwd = args.password or BLITZ_PASSWORD
    if not user or not pwd:
        sys.exit("⚠️ Identifiants Blitz manquants")

    # Conversion horaires locaux → UTC
    try:
        start_local = dt.datetime.fromisoformat(args.start)
        end_local = dt.datetime.fromisoformat(args.end)
    except ValueError:
        sys.exit("⛔ Format d’horodatage invalide (attendu : YYYY-MM-DD[T]HH:MM)")

    if start_local.tzinfo is None:
        start_local = start_local.replace(tzinfo=LOCAL_TZ)
    if end_local.tzinfo is None:
        end_local = end_local.replace(tzinfo=LOCAL_TZ)

    start_utc, end_utc = [d.astimezone(dt.timezone.utc) for d in (start_local, end_local)]

    # Prevent downloads beyond the current UTC time
    now_utc = dt.datetime.now(dt.timezone.utc)
    if end_utc > now_utc:
        print(f"⚠️  Fin demandée {end_utc} > maintenant ({now_utc}) : on lève à maintenant")
        end_utc = now_utc

    print(f"🔄 Téléchargement {start_utc} → {end_utc} UTC")
    print(f"Authentification : {user}")
    auth = (user, pwd)

    # Vérifie les timestamps déjà en base
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT timestamp FROM impacts")
        existing_timestamps = {row[0] for row in cur.fetchall()}

    # Créneaux à télécharger
    heures_a_telecharger = [
        ts for ts in daterange(start_utc, end_utc)
        if ts.isoformat() not in existing_timestamps
    ]

    if not heures_a_telecharger:
        print("✅ Rien à faire : tous les créneaux sont déjà en base.")
        return

    # Téléchargement parallèle avec suivi
    progress = tqdm(total=len(heures_a_telecharger), desc="Téléchargements", unit="créneau")
    with ThreadPoolExecutor(max_workers=args.threads) as pool:
        futures = {
            pool.submit(download_one, ts, auth, args.retry): ts
            for ts in heures_a_telecharger
        }
        for fut in as_completed(futures):
            ts = futures[fut]
            result = fut.result()
            progress.update(1)
            print(f"{ts:%H:%M} {'✔' if result else '✘'}")
            logging.info(f"{ts.isoformat()} {'OK' if result else 'absent'}")
    progress.close()
    print("✅ Script terminé. Base SQLite mise à jour.")
    logging.info("Fin du script.")

# ----------------------------------------------------------------------
# Petit adaptateur pour la CLI -------------------------
def main_cli(ns: argparse.Namespace) -> None:
    """
    Adaptateur fin qui reçoit le Namespace construit par cli.py
    et ré‑appelle le vrai parseur interne de ce script.

    Le principe : on reconstruit une liste d'arguments comme s’ils
    venaient de la ligne de commande, puis on appelle `main()` après
    avoir « monkey‑patché » sys.argv. Aucune logique métier n’est dupliquée.
    """
    argv = [__file__]

    # ordre défini par _parse_args()
    argv.extend([ns.start, ns.end])

    if ns.login:
        argv.extend(["--login", ns.login])
    if ns.password:
        argv.extend(["--password", ns.password])
    if getattr(ns, "threads", None):
        argv.extend(["--threads", str(ns.threads)])
    if getattr(ns, "retry", None):
        argv.extend(["--retry", str(ns.retry)])
    if getattr(ns, "log", None):
        argv.extend(["--log", ns.log])

    # Sauvegarde/restaure sys.argv
    _old_argv = sys.argv
    try:
        sys.argv = argv
        main()  # appel de la fonction principale existante
    finally:
        sys.argv = _old_argv

if __name__ == "__main__":
    main()