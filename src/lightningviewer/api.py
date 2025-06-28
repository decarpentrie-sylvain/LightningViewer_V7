"""lightningviewer.api
====================
Point d’entrée programmatique unique pour la V7.  Tout autre code
(app GUI, CLI ou notebooks) importe exclusivement depuis ce module.

Fonctions exposées
------------------
- download_range(start_iso, end_iso, *, threads=4, login=None, password=None, **kwargs)
- query_impacts(start_iso, end_iso, *, center_lat=None, center_lon=None,
                rayon_km=None, as_dataframe=True)
- build_kmz(df, output_path, *, center_lat=None, center_lon=None,
            rayon_km=None, open_after=False)
- purge_old(days=15)

Chaque fonction délègue au module interne existant (download, query, kmz,
 purge) puis renvoie un résultat simple.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional
import argparse

from . import _lazy_import  # util interne (ajouté plus bas)

# Racine du projet
ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "blitz.db"

###############################################################################
# Téléchargement
###############################################################################

def download_range(
    start_iso: str,
    end_iso: str,
    *,
    threads: int = 4,
    login: Optional[str] = None,
    password: Optional[str] = None,
    **kwargs,
) -> None:
    """Télécharge puis insère en base tous les créneaux 10′ entre *start* et
    *end*.
    Accepte les mêmes options que le script CLI (threads, retry, etc.).
    """
    dl = _lazy_import("lightningviewer.blitz_range_download_V7")
    # Build a namespace matching CLI args
    ns = argparse.Namespace(
        start=start_iso,
        end=end_iso,
        threads=threads,
        login=login,
        password=password,
        **kwargs,
    )
    try:
        dl.main_cli(ns)
    except TypeError as e:
        # fallback if threads unsupported
        if "unexpected keyword argument 'threads'" in str(e):
            ns2 = argparse.Namespace(
                start=start_iso,
                end=end_iso,
                login=login,
                password=password,
                **kwargs,
            )
            dl.main_cli(ns2)
        else:
            raise

###############################################################################
# Requête SQL
###############################################################################

def query_impacts(
    start_iso: str,
    end_iso: str,
    *,
    center_lat: float | None = None,
    center_lon: float | None = None,
    rayon_km: float | None = None,
    as_dataframe: bool = True,
):
    """Retourne les impacts entre *start* et *end* optionnellement filtrés
    dans un disque *(center_lat, center_lon, rayon_km)*.
    - *as_dataframe* : True → pandas.DataFrame, False → liste de tuples.
    """
    mod = _lazy_import("blitz_query")
    df = mod.requete_impacts(
        datetime.fromisoformat(start_iso),
        datetime.fromisoformat(end_iso),
        center_lat=center_lat,
        center_lon=center_lon,
        rayon_km=rayon_km,
    )
    return df if as_dataframe else list(df.itertuples(index=False))

###############################################################################
# KMZ
###############################################################################

def build_kmz(
    df,
    output_path: str | Path,
    *,
    center_lat: float | None = None,
    center_lon: float | None = None,
    rayon_km: float | None = None,
    open_after: bool = False,
) -> Path:
    """Construit un KMZ à partir d’un *DataFrame* (ou équivalent).
    - *output_path*          : chemin cible (créé/écrasé).
    - *center_lat/center_lon* : latitude/longitude du centre pour ajouter le repère violet et ajuster le zoom.
    - *rayon_km*              : filtre optionnel par rayon (km) autour de ce centre.
    - *open_after*            : si True, ouvre dans l’app par défaut (macOS : « open »).
    Retourne le `Path` du fichier créé.
    """
    kmz_mod = _lazy_import("build_kmz")
    path = Path(output_path)
    kmz_mod.build_kmz(
        df, path,
        center=(center_lat, center_lon) if center_lat is not None and center_lon is not None else None,
        rayon_km=rayon_km
    )

    if open_after:
        import subprocess, sys

        subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", str(path)], check=False)
    return path

###############################################################################
# Purge
###############################################################################

def purge_old(days: int = 15) -> int:
    """Supprime les impacts plus anciens que *days* jours.
    Retourne le nombre d’enregistrements supprimés."""
    purge = _lazy_import("purge_blitz")
    return purge.main_cli(days=days)

###############################################################################
# Lazy‑import helper (evite les dépendances circulaires)
###############################################################################

import importlib
from types import ModuleType

def _lazy_import(name: str) -> ModuleType:
    """
    Import a submodule of lightningviewer by name, always using the lightningviewer package prefix.
    """
    # Determine full module path
    pkg = __package__  # "lightningviewer.api" -> "lightningviewer"
    base = pkg.split(".", 1)[0]
    module_name = name if name.startswith(f"{base}.") else f"{base}.{name}"
    return importlib.import_module(module_name)