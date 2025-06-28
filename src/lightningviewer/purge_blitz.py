#!/usr/bin/env python3
"""
Purge automatique / manuelle de la base blitz.db

- Impacts vieux de plus de 15 jours ➜ supprimés
- Index R‑Tree tenu en cohérence
- Table `events` : on conserve
    • toutes les entrées des 15 derniers jours
    • les entrées plus anciennes mais créées il y a moins de 2 jours
  sauf si --disable-events-purge est passé.

Le module expose :

    * main(args)        → logique cœur
    * main_cli(ns=None) → point d’entrée appelé par lightningviewer.cli
    * exécution directe (python purge_blitz.py --help)

En important le module, AUCUNE action n’est exécutée : pas de parse_args
au niveau import, ce qui évite les conflits sys.argv dans la CLI globale.
"""
from __future__ import annotations

import argparse
import datetime as dt
import logging
import pathlib
import sqlite3
import warnings
import json
from lightningviewer._paths import DB_PATH as DB

# --------------------------------------------------------------------------- #
# Constantes & log                                                            #
# --------------------------------------------------------------------------- #
warnings.filterwarnings("ignore", category=DeprecationWarning)

ROOT = pathlib.Path(__file__).resolve().parents[1]
LOG  = pathlib.Path.home() / "Library/Logs" / "LightningViewer" / "purge.log"
LOG.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=LOG,
    level=logging.INFO,
    format="%(asctime)s - %(message)s"
)

# --------------------------------------------------------------------------- #
# Parser -------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Purge automatique ou manuelle des données blitz.db."
    )
    p.add_argument(
        "--disable-events-purge",
        action="store_true",
        help="Ne pas supprimer les événements plus anciens que 15 jours"
    )
    p.add_argument(
        "--manual-start",
        type=str,
        default=None,
        help="Date de début ISO pour une purge manuelle"
    )
    p.add_argument(
        "--manual-end",
        type=str,
        default=None,
        help="Date de fin ISO pour une purge manuelle"
    )
    p.add_argument(
        "--days",
        type=int,
        default=15,
        help="Âge max (en jours) des impacts à conserver (défaut : 15)"
    )
    return p

# --------------------------------------------------------------------------- #
# Logique cœur -------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
def main(args: argparse.Namespace) -> None:
    """Exécute la purge selon les arguments déjà parsés."""

    # --- détermination de la fenêtre à purger --------------------------------
    now = dt.datetime.utcnow()

    # Fenêtre d’âge pour les impacts (ex : 15 jours)
    impacts_cutoff = now - dt.timedelta(days=args.days)

    # Fenêtre de conservation « récente » pour la table events (toujours 2 jours)
    keep_recent   = now - dt.timedelta(days=2)

    if args.manual_start and args.manual_end:
        # Mode manuel : on respecte la période de l’utilisateur
        cutoff_end = args.manual_end           # utilisé plus bas pour le log
        purge_mode = "manuelle"
    else:
        # Mode automatique : on purge tout ce qui est plus vieux que <impacts_cutoff>
        cutoff_end = impacts_cutoff.isoformat()
        purge_mode = "automatique"

    # --- connexion SQLite ----------------------------------------------------
    with sqlite3.connect(DB) as conn:
        cur = conn.cursor()

        # S'assure que la table events existe (historique des opérations)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS events (
                timestamp     TEXT NOT NULL,
                event_type    TEXT,
                details       TEXT,
                event_period  TEXT
            )
        """)

        # Optim : WAL + index timestamp
        cur.execute("PRAGMA journal_mode = WAL;")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_impacts_timestamp
            ON impacts(timestamp);
        """)

        # Purge table impacts -------------------------------------------------
        cur.execute("DELETE FROM impacts WHERE timestamp < ?", (impacts_cutoff.isoformat(),))
        impacts_deleted = cur.rowcount

        # Purge table events --------------------------------------------------
        events_deleted = 0
        if not args.disable_events_purge:
            # Supprime :
            #   • événements trop vieux (timestamp < keep_recent)
            #   • ET concernant une période elle‑même trop vieille (event_period < impacts_cutoff)
            cur.execute("""
                DELETE FROM events
                WHERE timestamp < ?
                  AND (
                        event_period IS NULL
                        OR event_period < ?
                      )
            """, (keep_recent.isoformat(), impacts_cutoff.isoformat()))
            events_deleted = cur.rowcount

        # Nettoyage index R‑Tree ---------------------------------------------
        cur.execute("""
            DELETE FROM impacts_rtree
            WHERE id NOT IN (SELECT rowid FROM impacts)
        """)

        # Trace la purge dans la table events
        cur.execute("""
            INSERT INTO events (timestamp, event_type, details, event_period)
            VALUES (?, ?, ?, ?)
        """, (
            now.isoformat(timespec="seconds"),
            "purge",
            json.dumps({
                "impacts_deleted": impacts_deleted,
                "events_deleted": events_deleted,
                "mode": purge_mode
            }),
            f"-∞ / < {impacts_cutoff.date().isoformat()}"
        ))

        conn.commit()
        cur.execute("VACUUM")

    # --- logs & stdout -------------------------------------------------------
    logging.info(
        "Purge %s : %d impacts, %d événements supprimés (cutoff=%s)",
        purge_mode, impacts_deleted, events_deleted, cutoff_end
    )

    print(f"✅ Purge {purge_mode} : {impacts_deleted} impacts supprimés avant {cutoff_end}.")
    if not args.disable_events_purge:
        print(f"ℹ️  {events_deleted} événements purgés également.")
    else:
        print("ℹ️  Événements conservés (--disable-events-purge)")

# --------------------------------------------------------------------------- #
# Adaptateur CLI pour lightningviewer.cli ----------------------------------- #
# --------------------------------------------------------------------------- #
def main_cli(ns: argparse.Namespace | None = None) -> None:
    """Point d’entrée appelé par lightningviewer.cli."""
    if ns is None:
        ns = _build_parser().parse_args()
    main(ns)

# --------------------------------------------------------------------------- #
# Exécution directe --------------------------------------------------------- #
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    main_cli()