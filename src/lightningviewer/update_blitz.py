#!/usr/bin/env python3
"""
Mise à jour incrémentale de la base blitz.db.
- Détecte la plage manquante
- Télécharge via blitz_range_download_V7.py
- Retourne 0 (ok) ou 1 (échec) pour que launchd notifie en cas d'erreur.
"""
import pathlib, sqlite3, datetime as dt, subprocess, sys, logging, json, time

ROOT   = pathlib.Path(__file__).resolve().parents[2]        # dossier projet
DB     = ROOT / "data" / "blitz.db"
DOWNLOADER = pathlib.Path(__file__).with_name("blitz_range_download_V7.py")  # même dossier que ce fichier
if not DOWNLOADER.exists():
    logging.error("Fichier téléchargeur introuvable : %s", DOWNLOADER)
    sys.exit(1)
LOG    = pathlib.Path.home() / "Library/Logs/LightningViewer/update.log"

# Create log directory if it doesn't exist
LOG.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(filename=LOG, level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")


def notify(message: str) -> None:
    """
    Affiche une notification macOS pour l'utilisateur final.
    Utilise AppleScript ; si l'appel échoue, on écrit simplement dans le log.
    """
    try:
        subprocess.run(
            ["osascript", "-e", f'display notification \"{message}\" with title \"LightningViewer\"'],
            check=False
        )
    except Exception as exc:
        logging.warning("Notification impossible : %s", exc)


# Helper to ensure the log_events table exists
def ensure_schema() -> None:
    """Crée la table log_events si elle n’existe pas encore."""
    try:
        with sqlite3.connect(DB) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS log_events (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT,
                    timestamp  TEXT,
                    details    TEXT
                )
                """
            )
    except Exception as exc:
        logging.warning("Impossible de créer/vérifier log_events : %s", exc)

def last_timestamp() -> dt.datetime | None:
    if not DB.exists():
        return None
    with sqlite3.connect(DB) as conn:
        row = conn.execute("SELECT MAX(timestamp) FROM impacts").fetchone()
        if row and row[0]:
            return dt.datetime.fromisoformat(row[0])
    return None

def _do_download() -> int:
    ensure_schema()          # garantit l’existence de log_events
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

    # Enregistrement de la tentative dans la base de données
    try:
        with sqlite3.connect(DB) as conn:
            conn.execute("""
                INSERT INTO log_events (event_type, timestamp, details)
                VALUES (?, ?, ?)
            """, ("download_attempt", dt.datetime.now(dt.timezone.utc).isoformat(), json.dumps({
                "start": start.isoformat(timespec="minutes"),
                "end": end_utc.isoformat(timespec="minutes")
            })))
    except Exception as e:
        logging.warning("Échec enregistrement tentative de téléchargement : %s", e)

    cmd = [sys.executable, str(DOWNLOADER),
           start.isoformat(timespec="minutes"),
           end_utc.isoformat(timespec="minutes"),
           "--threads", "8"]
    logging.info("Téléchargement %s → %s", start, end_utc)
    res = subprocess.run(cmd)
    if res.returncode == 0:
        logging.info("Mise à jour OK.")
        try:
            with sqlite3.connect(DB) as conn:
                conn.execute("""
                    INSERT INTO log_events (event_type, timestamp, details)
                    VALUES (?, ?, ?)
                """, ("download_success", dt.datetime.now(dt.timezone.utc).isoformat(), json.dumps({
                    "start": start.isoformat(timespec="minutes"),
                    "end": end_utc.isoformat(timespec="minutes")
                })))
        except Exception as e:
            logging.warning("Échec enregistrement succès de téléchargement : %s", e)
    else:
        logging.error("Échec mise à jour. Code %s", res.returncode)
        try:
            with sqlite3.connect(DB) as conn:
                conn.execute("""
                    INSERT INTO log_events (event_type, timestamp, details)
                    VALUES (?, ?, ?)
                """, ("download_error", dt.datetime.now(dt.timezone.utc).isoformat(), json.dumps({
                    "start": start.isoformat(timespec="minutes"),
                    "end": end_utc.isoformat(timespec="minutes"),
                    "returncode": res.returncode
                })))
        except Exception as e:
            logging.warning("Échec enregistrement échec de téléchargement : %s", e)
    return res.returncode


def main() -> int:
    """
    Effectue jusqu'à 4 tentatives (1 initiale + 3 reprises) espacées d'une heure.
    En cas d'échec, notifie l'utilisateur de l'heure de la prochaine tentative.
    """
    MAX_TRIES   = 4       # 1 essai + 3 reprises
    RETRY_DELAY = 3600    # secondes (1 h)

    for attempt in range(1, MAX_TRIES + 1):
        code = _do_download()
        if code == 0:
            return 0

        # Échec : prévenir l'utilisateur et patienter
        now_local  = dt.datetime.now().strftime("%H:%M")
        next_local = (dt.datetime.now() + dt.timedelta(seconds=RETRY_DELAY)).strftime("%H:%M")
        notify(f"Synchro Blitzortung a échoué à {now_local}. Prochaine tentative prévue à : {next_local}")

        if attempt < MAX_TRIES:
            time.sleep(RETRY_DELAY)

    # Tous les essais ont échoué
    notify("Synchro Blitzortung a échoué après 4 tentatives consécutives.")
    return 1

if __name__ == "__main__":
    sys.exit(main())