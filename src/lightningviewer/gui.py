#!/usr/bin/env python3
"""
Streamlit front‑end for LightningViewer V7
------------------------------------------

Launch with:

    streamlit run path/to/lightningviewer/gui.py

or, thanks to the CLI wrapper:

    lv gui
"""
from __future__ import annotations

import logging
logging.basicConfig(level=logging.INFO)

import math
import json
from lightningviewer.geocode import geocode_multi  # multi‑provider helper
from lightningviewer.api import download_range, query_impacts, build_kmz
from lightningviewer._paths import KMZ_PATH, ENV_FILE, DB_PATH

from dotenv import load_dotenv
# Load project .env explicitly
load_dotenv(dotenv_path=ENV_FILE)

import os
import pathlib
import shutil
import datetime as dt
import inspect
import argparse
from lightningviewer.blitz_range_download_V7 import main_cli as _full_dl
from typing import Optional

# simple in-memory cache for geocoding results
_GEO_CACHE: dict[str, tuple[float, float, str]] = {}

# read optional Google API key from environment
GOOGLE_KEY = os.getenv("GOOGLE_API_KEY", "")

import streamlit as st
from geopy.geocoders import Nominatim

def _reset_address():
    """Reset any previous address selection when the input query changes."""
    for key in ("sel_addr", "full_addr", "provider", "country", "lat_c", "lon_c"):
        st.session_state.pop(key, None)

def _on_select():
    """Store the selected geocoded address in session state."""
    global geo_candidates
    idx = st.session_state.sel_addr
    g = geo_candidates[idx]
    st.session_state["lat_c"] = g.lat
    st.session_state["lon_c"] = g.lon
    st.session_state["full_addr"] = g.label
    st.session_state["provider"] = g.provider
    st.session_state["country"] = g.label.split(",")[-1].strip()

# --- helpers ---------------------------------------------------------------

def _geo_dist_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great‑circle distance in km (haversine, quick)."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = phi2 - phi1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dl / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def _format_distance(d_km: float) -> str:
    return f"{d_km:.0f} km"

# --- simple in‑memory cache to spare geocoder calls (session‑wide) ----------


def _cleanup_previous() -> None:
    """Remove old KMZ to avoid confusion."""
    if KMZ_PATH.exists():
        KMZ_PATH.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Streamlit layout
# ---------------------------------------------------------------------------

st.set_page_config(page_title="LightningViewer V7", page_icon="⚡")

st.title("⚡ LightningViewer V7")

# ---------------------------------------------------------------------------
# Sidebar – interactive parameters
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Paramètres de l’étude")

    # --- address search / auto‑complete ------------------------------------
    # User input: reset any previous selection when the query changes
    typed = st.text_input(
        "Lieu ou adresse",
        value=st.session_state.get("typed_address", ""),
        key="typed_address",
        on_change=_reset_address,
        help="Commencez à taper pour voir les suggestions",
    )
    geo_candidates: list = []
    # Require at least 3 characters before searching
    if len(typed) < 3:
        st.info("Veuillez taper au moins 3 caractères pour lancer la recherche.")
        st.stop()
    # Perform geocoding once we have enough input
    with st.spinner("Recherche d’adresse…"):
        geo_candidates = geocode_multi(typed, max_results=5)
    if not geo_candidates:
        st.error("❌ Aucune adresse trouvée.")
        st.stop()

    # Trier par distance depuis la position utilisateur si disponible
    my_pos = st.session_state.get("my_pos")
    if my_pos:
        geo_candidates.sort(key=lambda g: _geo_dist_km(my_pos[0], my_pos[1], g.lat, g.lon))

    # Affichage des choix
    labels = [
        f"{g.label} ({g.provider.capitalize()})"
        for g in geo_candidates
    ]

    selected_label = st.selectbox(
        "Lieu ou adresse",
        options=labels,
        key="combo_addr",
        help="Commencez à taper pour voir les suggestions d'adresses",
        on_change=_on_select,
    )

    if selected_label in labels:
        idx = labels.index(selected_label)
        g = geo_candidates[idx]
        st.session_state["lat_c"] = g.lat
        st.session_state["lon_c"] = g.lon
        st.session_state["full_addr"] = g.label
        st.session_state["provider"] = g.provider
        st.session_state["country"] = g.label.split(",")[-1].strip()
        st.session_state["sel_addr"] = idx
    else:
        _reset_address()

    # --- radius ------------------------------------------------------------
    rayon_km = st.number_input(
        "Rayon (km)", min_value=1, max_value=1000,
        value=st.session_state.get("rayon_km", 20),
        step=1, key="rayon_km"
    )
    # --- dates -------------------------------------------------------------
    col1, col2 = st.columns(2)
    with col1:
        d_start = st.date_input("Date début", dt.date.today(), key="d_start")
    with col2:
        d_end = st.date_input("Date fin", dt.date.today(), key="d_end")

    col3, col4 = st.columns(2)
    with col3:
        t_start = st.time_input("Heure début", dt.time(0, 0))
    with col4:
        t_end = st.time_input("Heure fin", dt.time(23, 59))

    st.caption("Heures interprétées dans votre fuseau local puis converties en UTC.")

# ensure an address was explicitly selected
if "full_addr" not in st.session_state:
    st.warning("Veuillez sélectionner une adresse depuis la liste avant de continuer.")
    st.stop()

# Combine to UTC ISO‑8601
tz_local = dt.datetime.now().astimezone().tzinfo  # user's tz
start_dt_local = dt.datetime.combine(d_start, t_start).replace(tzinfo=tz_local)
end_dt_local = dt.datetime.combine(d_end, t_end).replace(tzinfo=tz_local)
start_iso_utc = start_dt_local.astimezone(dt.timezone.utc).isoformat()
end_iso_utc = end_dt_local.astimezone(dt.timezone.utc).isoformat()

# ---------------------------------------------------------------------------
# Processing
# ---------------------------------------------------------------------------

# --- reuse the selection from sidebar, no extra geocoding ---
lat_c     = st.session_state["lat_c"]
lon_c     = st.session_state["lon_c"]
full_addr = st.session_state["full_addr"]
provider  = st.session_state.get("provider", "")

# Retrieve saved address and country for geocoding
addr = st.session_state["full_addr"]
country = st.session_state["country"]
# Include country in query only if not already present
query_addr = addr if country.lower() in addr.lower() else f"{addr}, {country}"

st.success(f"📍 {full_addr} — ({lat_c:.4f}, {lon_c:.4f})")

# Ensure SQLite DB is initialized (create tables/index if missing)
from lightningviewer._paths import DB_PATH
if not DB_PATH.exists():
    import lightningviewer.init_db_blitz as _init_mod
    init_fn = getattr(_init_mod, "main_cli", None) or getattr(_init_mod, "main", None)
    if init_fn is None:
        st.error("Erreur interne : impossible d'initialiser la base de données.")
        st.stop()
    # call with args if it accepts them
    if len(inspect.signature(init_fn).parameters) == 0:
        init_fn()
    else:
        init_fn(argparse.Namespace())

# Download (full-range) the exact interval specified
with st.spinner("Téléchargement de la plage sélectionnée…"):
    try:
        print("DEBUG: About to call full-range download")
        ns_dl = argparse.Namespace(
            start=start_iso_utc,
            end=end_iso_utc,
            threads=8,
            login=os.getenv("BLITZ_LOGIN"),
            password=os.getenv("BLITZ_PASSWORD"),
        )
        _full_dl(ns_dl)
        print("DEBUG: full-range download completed without exception")
    except Exception as exc:
        print("DEBUG: _full_dl raised exception", exc)
        st.error(f"Erreur durant le téléchargement : {exc}")
        st.stop()

# Query DB
with st.spinner("Recherche des impacts…"):
    try:
        df = query_impacts(
            start_iso_utc, end_iso_utc, center_lat=lat_c, center_lon=lon_c, rayon_km=rayon_km
        )
    except FileNotFoundError as exc:
        st.error(str(exc))
        st.stop()

n = len(df)
if n == 0:
    st.info(
        f"⚠️ Aucun impact trouvé du "
        f"{start_dt_local.strftime('%d/%m/%Y %H:%M')} au "
        f"{end_dt_local.strftime('%d/%m/%Y %H:%M')} "
        f"dans un rayon de {rayon_km} km."
    )
else:
    st.success(f"✅ {n} impact(s) trouvé(s). Génération du KMZ…")
    _cleanup_previous()
    build_kmz(
        df,
        KMZ_PATH,
        center_lat=lat_c,
        center_lon=lon_c,
        rayon_km=rayon_km,
        open_after=True,  # ouvre Google Earth
    )
    st.download_button(
        label="📦 Télécharger le KMZ",
        data=KMZ_PATH.read_bytes(),
        file_name=KMZ_PATH.name,
        mime="application/vnd.google-earth.kmz",
    )
