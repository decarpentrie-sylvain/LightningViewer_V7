#!/usr/bin/env python3
import pathlib, sqlite3, datetime as dt, logging
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
ROOT = pathlib.Path(__file__).parent.parent
DB   = ROOT / "data" / "blitz.db"
LOG  = pathlib.Path.home() / "Library/Logs/LightningViewer/purge.log"
logging.basicConfig(filename=LOG, level=logging.INFO, format="%(asctime)s - %(message)s")

cutoff = (dt.datetime.utcnow() - dt.timedelta(days=15)).isoformat()
with sqlite3.connect(DB) as conn:
    cur = conn.cursor()
    # Performance tuning: use WAL mode and index timestamp
    cur.execute("PRAGMA journal_mode = WAL;")
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_impacts_timestamp
        ON impacts(timestamp);
    """)
    cur.execute("DELETE FROM impacts WHERE timestamp < ?", (cutoff,))
    deleted = cur.rowcount
    cur.execute("DELETE FROM impacts_rtree "
                "WHERE id NOT IN (SELECT rowid FROM impacts)")
    conn.commit()
    cur.execute("VACUUM")
logging.info("Purge terminée. Impacts antérieurs au %s supprimés.", cutoff)

# Message de sortie systématique
if deleted:
    print(f"✅ Purge terminée : {deleted} impacts antérieurs au {cutoff} supprimés.")
else:
    print(f"ℹ️  Purge exécutée : aucun impact antérieur au {cutoff} à supprimer.")