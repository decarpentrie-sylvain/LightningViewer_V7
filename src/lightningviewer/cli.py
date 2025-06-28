#!/usr/bin/env python3
"""
cli.py – CLI unifiée pour LightningViewer V7
======================================================

Utilisation rapide :

  lv download START_ISO END_ISO [--threads 8]
  lv query   --start ISO --end ISO --lat 48.85 --lon 2.35 --rayon 100 \
             [--kmz chemin.kmz] [--open]
  lv purge   [--days 15]

Les sous‐commandes ne font qu’appeler les fonctions déjà existantes :

* download → blitz_range_download_V7.main_cli  (fallback main)
* query    → blitz_query.requete_impacts + build_kmz.build_kmz
* purge    → purge_blitz.main_cli  (ou rien si non dispo)

Le script est pensé pour être déclaré comme *console‑script* :

    # dans setup.cfg ou pyproject.toml
    [options.entry_points]
    console_scripts =
        lv = "lightningviewer.cli:main"
"""
from __future__ import annotations

import argparse
import importlib
import inspect
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv
from lightningviewer._paths import ENV_FILE
# Load environment variables from project .env if it exists
if ENV_FILE.exists():
    load_dotenv(dotenv_path=str(ENV_FILE))

# Ensure the directory that contains this file (src/) is on sys.path
_SRC_DIR = Path(__file__).resolve().parent
if str(_SRC_DIR) not in sys.path:  # avoid duplicates
    sys.path.insert(0, str(_SRC_DIR))

from datetime import datetime as _dt, datetime, timezone

# ---------------------------------------------------------------------------
# Helpers --------------------------------------------------------------------
# ---------------------------------------------------------------------------


def _lazy_import(mod_name: str):
    """
    Importe un module à la demande.  
    Essaie d’abord le nom nu, puis « src.<nom> » si le premier échoue.
    """
    try:
        return importlib.import_module(mod_name)
    except ModuleNotFoundError:
        return importlib.import_module(f"src.{mod_name}")


def _iso(s: str) -> str:
    """Valide rapidement un horodatage ISO."""
    try:
        _dt.fromisoformat(s)
        return s
    except ValueError as exc:  # pragma: no cover
        raise argparse.ArgumentTypeError(f"Horodatage invalide : {s}") from exc


# ---------------------------------------------------------------------------
# Sub‑command implementations -------------------------------------------------
# ---------------------------------------------------------------------------


def _cmd_download(args: argparse.Namespace) -> None:
    """
    Appelle le script de téléchargement (blitz_range_download_V7).

    Compatibilité : le module peut exposer :
      * main_cli(args)   — signature avec Namespace
      * main(args)       — idem
      * main()           — signature sans argument
    On détecte la signature pour appeler correctement la fonction.
    """

    from datetime import datetime, timezone

    # Prevent downloading data for future timestamps
    try:
        start_dt = datetime.fromisoformat(args.start)
        end_dt   = datetime.fromisoformat(args.end)
        # Determine now in the same tz-awareness as the parsed end_dt
        if end_dt.tzinfo is None:
            now_cmp = datetime.utcnow()
        else:
            now_cmp = datetime.now(timezone.utc)
        if end_dt > now_cmp:
            print(f"⚠️  Date de fin {end_dt.isoformat()} est dans le futur, elle est remplacée par maintenant ({now_cmp.isoformat()}).")
            # Clamp end timestamp to now
            end_dt = now_cmp
            args.end = end_dt.isoformat()

        # Clamp start timestamp to at most 15 days back
        from datetime import timedelta
        min_start = now_cmp - timedelta(days=15)
        if start_dt < min_start:
            print(f"⚠️  Date de début {start_dt.isoformat()} est trop ancienne, elle est remplacée par {min_start.isoformat()} (15 j. max).")
            start_dt = min_start
            args.start = start_dt.isoformat()
    except Exception:
        # ignore parse errors and let later code handle invalid formats
        pass

    from ._paths import DB_PATH

    # Si la base n’existe pas, on l’init automatique via lazy import
    if not DB_PATH.exists():
        mod_init = _lazy_import("lightningviewer.init_db_blitz")
        init_fn = getattr(mod_init, "main_cli", None) or getattr(mod_init, "main", None)
        if init_fn is None:
            print("⚠️  init_db_blitz n’expose pas de fonction exécutable (main_cli/main).")
            sys.exit(1)
        # Call init function with or without args based on signature
        if len(inspect.signature(init_fn).parameters) == 0:
            init_fn()             # type: ignore[arg-type]
        else:
            init_fn(args)         # type: ignore[arg-type]
    mod = _lazy_import("blitz_range_download_V7")
    fn = (
        getattr(mod, "main_cli", None)
        or getattr(mod, "main", None)
    )
    if fn is None:
        print("⚠️  blitz_range_download_V7 n’expose aucune fonction exécutable (main/main_cli).")
        sys.exit(1)

    # Détection de la signature : si aucun paramètre, on n’en passe pas
    if len(inspect.signature(fn).parameters) == 0:
        fn()            # type: ignore[arg-type]
    else:
        fn(args)        # type: ignore[arg-type]

    # ─── Purge old impacts (>15 days) after download ─────────────────────────
    from argparse import Namespace

    mod_purge = _lazy_import("purge_blitz")
    purge_fn = getattr(mod_purge, "main_cli", None)
    if purge_fn:
        # Lance la purge avec un Namespace minimal (uniquement --days)
        purge_fn(Namespace(
            disable_events_purge=False,
            manual_start=None,
            manual_end=None,
            days=15,
        ))


def _cmd_query(args: argparse.Namespace) -> None:
    requete_impacts = _lazy_import("blitz_query").requete_impacts
    build_kmz = _lazy_import("build_kmz").build_kmz

    start_dt = _dt.fromisoformat(args.start)
    end_dt = _dt.fromisoformat(args.end)

    df = requete_impacts(
        start_dt,
        end_dt,
        center_lat=args.lat,
        center_lon=args.lon,
        rayon_km=args.rayon,
    )
    if df.empty:
        print("Aucun impact dans la zone/temps demandé.")
        return

    kmz_path = Path(args.kmz or f"impacts_{int(args.rayon)}km.kmz")
    build_kmz(df, str(kmz_path))
    print(f"✅ KMZ écrit : {kmz_path.resolve()}")

    if args.open:  # ouvre dans Google Earth (macOS “open”, sinon xdg‑open)
        opener = "open" if sys.platform == "darwin" else "xdg-open"
        try:
            subprocess.run([opener, str(kmz_path.resolve())], check=False)
        except FileNotFoundError:
            print(f"ℹ️  Impossible de lancer {opener}")


def _cmd_purge(args: argparse.Namespace) -> None:
    mod = _lazy_import("purge_blitz")
    fn = getattr(mod, "main_cli", None)
    if fn:
        fn(args)
    else:
        # simple fallback : exécute le module comme script
        import runpy 

        runpy.run_module("purge_blitz", run_name="__main__")


# ---------------------------------------------------------------------------
# GUI -----------------------------------------------------------------------
# ---------------------------------------------------------------------------


def _cmd_gui(args: argparse.Namespace) -> None:
    """
    Lance l’interface graphique Streamlit.

    On exécute simplement :

        streamlit run <chemin>/lightningviewer/gui.py

    et on relaie la sortie du processus.  Aucune option particulière
    n’est gérée pour l’instant ; Streamlit affiche l’URL locale une fois
    lancé.
    """
    # Recherche du script Streamlit dans plusieurs emplacements possibles
    candidate_paths = [
        _SRC_DIR / "gui.py",                       # cas classique : src/lightningviewer/gui.py
        _SRC_DIR / "lightningviewer" / "gui.py",   # cas « sous‑paquet »
    ]
    gui_script = next((p for p in candidate_paths if p.exists()), None)

    if gui_script is None:
        print("⚠️  Aucun fichier GUI (gui.py) trouvé dans les chemins attendus.")
        sys.exit(1)

    try:
        subprocess.run(["streamlit", "run", str(gui_script)], check=False)
    except FileNotFoundError:
        print("❌ Streamlit n’est pas installé (pip install streamlit).")


# ---------------------------------------------------------------------------
# Argument parser ------------------------------------------------------------
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="lv",
        description="LightningViewer V7 – outil en ligne de commande",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    # --- download -----------------------------------------------------------
    dl = sub.add_parser("download", help="Télécharge et met à jour la base")
    dl.add_argument("start", type=_iso, help="Horodatage début ISO (locale ok)")
    dl.add_argument("end", type=_iso, help="Horodatage fin ISO")
    dl.add_argument("--threads", type=int, default=4, help="Threads (par défaut 4)")
    dl.add_argument("--retry", type=int, default=3, help="Tentatives réseau")
    dl.add_argument("--login", help="Login Blitzortung (override .env)")
    dl.add_argument("--password", help="Password Blitzortung")
    dl.set_defaults(func=_cmd_download)

    # --- query --------------------------------------------------------------
    q = sub.add_parser("query", help="Extrait les impacts & génère un KMZ")
    q.add_argument("--start", required=True, type=_iso)
    q.add_argument("--end", required=True, type=_iso)
    q.add_argument("--lat", required=True, type=float, help="Latitude centre")
    q.add_argument("--lon", required=True, type=float, help="Longitude centre")
    q.add_argument("--rayon", type=float, default=100, help="Rayon km")
    q.add_argument("--kmz", help="Chemin de sortie (.kmz)")
    q.add_argument("--open", action="store_true", help="Ouvre le KMZ à la fin")
    q.set_defaults(func=_cmd_query)

    # --- purge --------------------------------------------------------------
    pg = sub.add_parser("purge", help="Purge les impacts trop anciens")
    pg.add_argument("--days", type=int, default=15, help="Âge max en jours")
    pg.set_defaults(func=_cmd_purge)

    # --- gui ----------------------------------------------------------------
    g = sub.add_parser("gui", help="Lance l’interface graphique Streamlit")
    g.set_defaults(func=_cmd_gui)

    return p


# ---------------------------------------------------------------------------
# Entry point ----------------------------------------------------------------
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    args.func(args)  # appelle la bonne sous‑commande
    return 0


if __name__ == "__main__":
    sys.exit(main())
