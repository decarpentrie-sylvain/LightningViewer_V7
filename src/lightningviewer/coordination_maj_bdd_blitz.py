

#!/usr/bin/env python3
"""
coordination_maj_bdd_blitz.py

Script de coordination intelligente des tâches de maintenance de la base Blitz :
- Détermine s’il faut lancer un téléchargement incrémental (update_blitz)
- Détermine s’il faut lancer une purge (purge_blitz)
- Évite les doublons, respecte un rythme raisonnable, logue les décisions
"""

import pathlib
import sqlite3
import datetime as dt
import subprocess
import logging
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
DB = ROOT / "data" / "blitz.db"
LOG = pathlib.Path.home() / "Library/Logs/LightningViewer/coordination.log"
UPDATE_SCRIPT = ROOT / "src" / "lightningviewer" / "update_blitz.py"
PURGE_SCRIPT = ROOT / "src" / "lightningviewer" / "purge_blitz.py"

logging.basicConfig(filename=LOG, level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")

def should_run_update() -> bool:
    """Retourne True si une mise à jour est nécessaire (pas déjà faite depuis 8h)."""
    try:
        with sqlite3.connect(DB) as conn:
            # S'assure que la table log_events existe
            conn.execute("""
                CREATE TABLE IF NOT EXISTS log_events (
                    event_type TEXT,
                    timestamp  TEXT,
                    details    TEXT
                )
            """)
            row = conn.execute("""
                SELECT MAX(timestamp) FROM log_events
                WHERE event_type = 'download_success'
            """).fetchone()
            if row and row[0]:
                last_success = dt.datetime.fromisoformat(row[0])
                if last_success.tzinfo is None:
                    last_success = last_success.replace(tzinfo=dt.timezone.utc)
                delta = dt.datetime.now(dt.timezone.utc) - last_success
                return delta.total_seconds() > 8 * 3600
            return True
    except Exception as e:
        logging.warning("Échec de lecture dernière mise à jour : %s", e)
        return True

def should_run_purge() -> bool:
    """
    Retourne True si la dernière purge date de plus de 24 h.
    On interroge d'abord la nouvelle table « events ». Si elle n’existe pas
    encore (ancienne installation), on revient à log_events pour conserver
    la compatibilité ascendante.
    """
    cutoff = 24 * 3600  # secondes
    query  = "SELECT MAX(timestamp) FROM {table} WHERE event_type = 'purge'"

    try:
        with sqlite3.connect(DB) as conn:
            # S'assure que la table log_events existe
            conn.execute("""
                CREATE TABLE IF NOT EXISTS log_events (
                    event_type TEXT,
                    timestamp  TEXT,
                    details    TEXT
                )
            """)
            # ‑‑ priorité à la table events (schema V7)
            try:
                row = conn.execute(query.format(table="events")).fetchone()
            except sqlite3.OperationalError:
                # Table absente ⇒ fallback vers log_events (schema V6)
                row = conn.execute(query.format(table="log_events")).fetchone()

            if row and row[0]:
                last_purge = dt.datetime.fromisoformat(row[0])
                if last_purge.tzinfo is None:
                    last_purge = last_purge.replace(tzinfo=dt.timezone.utc)
                delta = dt.datetime.now(dt.timezone.utc) - last_purge
                return delta.total_seconds() > cutoff
            return True
    except Exception as e:
        logging.warning("Échec de lecture dernière purge : %s", e)
        return True

def run_script(script_path: pathlib.Path, label: str) -> None:
    """Exécute un script externe en subprocess."""
    try:
        result = subprocess.run([sys.executable, str(script_path)])
        if result.returncode == 0:
            logging.info("✅ Script %s exécuté avec succès.", label)
        else:
            logging.error("❌ Échec à l’exécution de %s (code %s)", label, result.returncode)
    except Exception as e:
        logging.error("❌ Erreur lors de l’appel de %s : %s", label, e)

def main():
    if should_run_update():
        logging.info("Déclenchement de la mise à jour Blitz")
        run_script(UPDATE_SCRIPT, "update_blitz.py")
    else:
        logging.info("Téléchargement non nécessaire (récemment effectué).")

    if should_run_purge():
        logging.info("Déclenchement de la purge Blitz")
        run_script(PURGE_SCRIPT, "purge_blitz.py")
    else:
        logging.info("Purge non nécessaire (récemment effectuée).")

if __name__ == "__main__":
    main()