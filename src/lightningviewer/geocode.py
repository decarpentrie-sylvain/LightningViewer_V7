"""
lightningviewer.geocode
-----------------------

Petit module d’auto‑géocodage.

* On tente d’abord Nominatim (OpenStreetMap) – aucune clé requise.
* En cas d’échec ou d’aucun résultat, on tente Google Maps Geocoding
  **si** la variable d’environnement `GOOGLE_API_KEY` est disponible.

La fonction publique :

    >>> geocode("Toulouse, France")
    (43.6045, 1.4440, "nominatim")

Renvoie un triplet (lat, lon, provider) ou lève une ValueError
si aucune des deux méthodes ne donne de résultat.
"""

from __future__ import annotations

import os
import time
import urllib.parse as _ulib
from typing import Literal, NamedTuple, List

import requests
from dotenv import load_dotenv

# Charge le .env à tout hasard (support CLI ou Streamlit lancé hors racine)
load_dotenv()

# ──────────────────────────────────────────────────────────────
# Config globale
# ──────────────────────────────────────────────────────────────
_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_GOOGLE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
_GOOGLE_KEY = os.getenv("GOOGLE_API_KEY", "").strip()
# User‑Agent conforme à la politique Nominatim : nom d’app + contact
_UA = (
    "LightningViewer/6 (https://github.com/your-repo; "
    "contact: svdvet@orange.fr)"
)

# Temps mini entre 2 appels Nominatim (politique 1 req / s)
_NOMINATIM_COOLDOWN = 1.1
_last_nominatim_call = 0.0

# ──────────────────────────────────────────────────────────────
# Nominatim
# ──────────────────────────────────────────────────────────────
def _geocode_nominatim(
    query: str,
    limit: int = 1,
) -> list[tuple[float, float, str]] | None:
    """Renvoie une liste de (lat, lon, label) ou None."""
    global _last_nominatim_call
    # Respecte le rate‑limit public de Nominatim
    delta = time.time() - _last_nominatim_call
    if delta < _NOMINATIM_COOLDOWN:
        time.sleep(_NOMINATIM_COOLDOWN - delta)

    params = {
        "q": query,
        "format": "json",
        "limit": limit,
        "accept-language": "fr",
    }
    try:
        r = requests.get(_NOMINATIM_URL, params=params, timeout=8,
                         headers={"User-Agent": _UA})
        _last_nominatim_call = time.time()
        r.raise_for_status()
        data = r.json()
        if not data:
            return None
        results = []
        for item in data:
            lat, lon = float(item["lat"]), float(item["lon"])
            label = item.get("display_name", query)
            results.append((lat, lon, label))
        return results
    except Exception:
        return None


# ──────────────────────────────────────────────────────────────
# Google Geocoding API
# ──────────────────────────────────────────────────────────────
def _geocode_google(query: str) -> list[tuple[float, float, str]] | None:
    """Renvoie une liste de (lat, lon, label) via Google Maps ou None."""
    if not _GOOGLE_KEY:
        return None

    params = {
        "address": query,
        "key": _GOOGLE_KEY,
    }
    try:
        r = requests.get(_GOOGLE_URL, params=params, timeout=8)
        r.raise_for_status()
        js = r.json()
        if js.get("status") != "OK" or not js.get("results"):
            return None
        results = []
        for result in js["results"]:
            loc = result["geometry"]["location"]
            lat, lon = float(loc["lat"]), float(loc["lng"])
            label = result.get("formatted_address", query)
            results.append((lat, lon, label))
        return results
    except Exception:
        return None


# ──────────────────────────────────────────────────────────────
# API publique
# ──────────────────────────────────────────────────────────────
Provider = Literal["nominatim", "google"]

def geocode(query: str) -> tuple[float, float, Provider]:
    """
    Géocode *query* et renvoie (lat, lon, provider).

    Stratégie :
      1. Nominatim (gratuit)
      2. Google Maps (si clé dispo)

    Lève ValueError si aucun fournisseur ne trouve.
    """
    query = query.strip()
    if not query:
        raise ValueError("Query vide")

    res = _geocode_nominatim(query)
    if res:
        lat, lon, _label = res[0]
        return (lat, lon, "nominatim")  # type: ignore[misc]

    res = _geocode_google(query)
    if res:
        lat, lon, _label = res[0]
        return (lat, lon, "google")  # type: ignore[misc]

    raise ValueError(f"Aucun résultat pour « {query} »")

class Address(NamedTuple):
    lat: float
    lon: float
    label: str
    provider: Provider

def geocode_multi(query: str, max_results: int = 5) -> List[Address]:
    """
    Géocode *query* et renvoie une liste d'Address (lat, lon, label, provider).

    Stratégie :
      1. Nominatim (gratuit) avec jusqu'à max_results résultats
      2. Google Maps (si clé dispo) si aucun résultat Nominatim

    Renvoie une liste vide si aucun résultat.
    """
    query = query.strip()
    if not query:
        return []

    from .geocode import _geocode_nominatim, _geocode_google, Address

    # Tente Nominatim
    results = _geocode_nominatim(query, limit=max_results)
    if results:
        return [Address(lat, lon, label, "nominatim") for lat, lon, label in results]

    # Sinon Google
    results = _geocode_google(query)
    if results:
        limited = results[:max_results]
        return [Address(lat, lon, label, "google") for lat, lon, label in limited]

    return []

__all__ = ["geocode", "geocode_multi", "Address"]