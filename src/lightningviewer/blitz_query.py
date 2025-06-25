import sqlite3
import pandas as pd
from typing import Optional, Union
from datetime import datetime
import math
from lightningviewer import _paths as paths

DB_PATH = paths.DB_PATH

def requete_impacts(
    start: Union[datetime, str],
    end: Union[datetime, str],
    center_lat: Optional[float] = None,
    center_lon: Optional[float] = None,
    rayon_km: Optional[float] = None
) -> pd.DataFrame:
    """
    Récupère les impacts entre deux dates, avec filtrage optionnel par zone autour d’un point.

    Args:
        start (datetime | str): Date/heure UTC de début
        end (datetime | str): Date/heure UTC de fin
        center_lat (float, optional): Latitude du point central
        center_lon (float, optional): Longitude du point central
        rayon_km (float, optional): Rayon en kilomètres

    Returns:
        pd.DataFrame: Résultat contenant timestamp, lat, lon, mcg
    """
    # Autoriser soit datetime, soit ISO 8601 str
    if isinstance(start, str):
        start = datetime.fromisoformat(start)
    if isinstance(end, str):
        end = datetime.fromisoformat(end)

    if not DB_PATH.exists():
        raise FileNotFoundError(f"Base SQLite introuvable : {DB_PATH.resolve()}")

    query_base = """
        SELECT timestamp, lat, lon, mcg
        FROM impacts
        WHERE timestamp BETWEEN ? AND ?
    """
    params = [start.isoformat(), end.isoformat()]

    # Si filtrage spatial
    if None not in (center_lat, center_lon, rayon_km):
        lat_min = center_lat - rayon_km / 111
        lat_max = center_lat + rayon_km / 111
        lon_scale = 111 * max(0.01, math.cos(math.radians(center_lat)))
        lon_min = center_lon - rayon_km / lon_scale
        lon_max = center_lon + rayon_km / lon_scale

        query_base += """
            AND rowid IN (
                SELECT id FROM impacts_rtree
                WHERE min_lat <= ? AND max_lat >= ?
                  AND min_lon <= ? AND max_lon >= ?
            )
        """
        # ⚠️  L’ordre des bornes doit correspondre aux quatre clauses de la
        #     sous‑requête R‑Tree : min_lat<=lat_max ; max_lat>=lat_min ; min_lon<=lon_max ; max_lon>=lon_min
        params += [lat_max, lat_min, lon_max, lon_min]

    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query(query_base, conn, params=params)
    return df