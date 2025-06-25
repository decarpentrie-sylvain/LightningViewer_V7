#!/usr/bin/env python3
"""
Mise à jour incrémentale de la base blitz.db.
- Détecte la plage manquante
- Télécharge via blitz_range_download_V7.py
- Retourne 0 (ok) ou 1 (échec) pour que launchd notifie en cas d'erreur.
"""
import pathlib, sqlite3, datetime as dt, subprocess, sys, os, logging

ROOT   = pathlib.Path(__file__).parent.parent          # dossier projet
DB     = ROOT / "data" / "blitz.db"
DOWNLOADER = ROOT / "src" / "blitz_range_download_V7.py"
LOG    = pathlib.Path.home() / "Library/Logs/LightningViewer/update.log"

# Create log directory if it doesn't exist
LOG.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(filename=LOG, level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")

def last_timestamp() -> dt.datetime | None:
    if not DB.exists():
        return None
    with sqlite3.connect(DB) as conn:
        row = conn.execute("SELECT MAX(timestamp) FROM impacts").fetchone()
        if row and row[0]:
            return dt.datetime.fromisoformat(row[0])
    return None

def main() -> int:
    # Current UTC time rounded down to nearest 10‑minute mark (tz‑aware)
    now_utc = dt.datetime.now(dt.timezone.utc)
    now_utc = now_utc.replace(
        microsecond=0,
        second=0,
        minute=(now_utc.minute // 10) * 10
    )
    end_utc = now_utc - dt.timedelta(minutes=30)          # sécurité 30 min
    start = last_timestamp()
    if start is None:
        # première exécution : 15 jours glissants
        start = end_utc - dt.timedelta(days=15)
    else:
        start += dt.timedelta(minutes=10)                 # créneau suivant

    # Ensure start is timezone‑aware in UTC
    if start.tzinfo is None:
        start = start.replace(tzinfo=dt.timezone.utc)

    if start >= end_utc:
        logging.info("Base déjà à jour (rien à télécharger).")
        return 0

    cmd = [sys.executable, str(DOWNLOADER),
           start.isoformat(timespec="minutes"),
           end_utc.isoformat(timespec="minutes"),
           "--threads", "8"]
    logging.info("Téléchargement %s → %s", start, end_utc)
    res = subprocess.run(cmd)
    if res.returncode == 0:
        logging.info("Mise à jour OK.")
    else:
        logging.error("Échec mise à jour. Code %s", res.returncode)
    return res.returncode

if __name__ == "__main__":
    sys.exit(main())