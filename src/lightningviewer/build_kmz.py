#!/usr/bin/env python3
"""
build_kmz.py
------------

Utility module to turn a pandas DataFrame of lightning impacts into a
Google Earth‑compatible **KMZ** file.

Expected DataFrame columns
--------------------------
* ``timestamp``  (ISO 8601 str or datetime)  
* ``lat`` / ``lon`` (float)  
* ``mcg`` (optional, int – max circular gap; used for colour coding)

Public functions
----------------
``build_kmz(df, output_path, *, name="impacts", center=None)``

Example
~~~~~~~
```python
from build_kmz import build_kmz
build_kmz(df, "impacts.kmz",
          name="Impacts France",
          center=(48.8566, 2.3522))
```
"""
from __future__ import annotations

import math
import os
import zipfile
from datetime import datetime, timezone
from tzlocal import get_localzone
from pathlib import Path
from typing import Iterable

import pandas as pd
from pandas import DataFrame


# --------------------------------------------------------------------------- #
# Internal helpers                                                            #
# --------------------------------------------------------------------------- #
def _kml_color(rgb_hex: str, alpha: str = "ff") -> str:
    """
    Convert ``#rrggbb`` to the aabbggrr format expected by KML.
    Default alpha = ``ff`` (opaque).  Example::

        >>> _kml_color("#ff0000")
        'ff0000ff'
    """
    rr, gg, bb = rgb_hex[1:3], rgb_hex[3:5], rgb_hex[5:7]
    return f"{alpha}{bb}{gg}{rr}"


def _style_block(style_id: str, rgb: str, scale: float = 0.8) -> str:
    """Return a ``<Style>`` block for a coloured circular placemark."""
    return f"""
  <Style id="{style_id}">
    <IconStyle>
      <scale>{scale}</scale>
      <color>{_kml_color(rgb)}</color>
      <Icon>
        <href>http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png</href>
      </Icon>
    </IconStyle>
  </Style>
""".rstrip()


def _center_style_block() -> str:
    """Fluorescent‑pink push‑pin for the centre marker (slightly larger)."""
    return """
  <Style id="center">
    <IconStyle>
      <scale>1.8</scale>
      <color>ffff66ff</color> <!-- aabbggrr => opaque + pink -->
      <Icon>
        <href>http://maps.google.com/mapfiles/kml/shapes/pushpin.png</href>
      </Icon> 
    </IconStyle>
  </Style>
""".rstrip()


def _style_for_mcg(mcg: float | None) -> str:
    """
    Return the KML style id based on *mcg* value.

    Colour scale (empirical):
        – mcg < 150 °  → red  
        – mcg < 300 °  → orange  
        – else         → yellow  
        – NaN          → grey
    """
    if mcg is None or (isinstance(mcg, float) and math.isnan(mcg)):
        return "grey"
    if mcg < 150:
        return "red"
    if mcg < 300:
        return "orange"
    return "yellow"


def _geo_dist_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great‑circle distance in km (haversine)."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = phi2 - phi1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dl / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# Mapping style id → RGB
_STYLE_RGB = {
    "red": "#ff0000",
    "orange": "#ff7f00",
    "yellow": "#ffff00",
    "grey": "#7f7f7f",
}


# --------------------------------------------------------------------------- #
# Public API                                                                  #
# --------------------------------------------------------------------------- #
def build_kmz(
    df: DataFrame,
    output_path: str | os.PathLike,
    *,
    name: str = "impacts",
    center: tuple[float, float] | None = None,
    rayon_km: float | None = None,
) -> Path:
    """
    Build a KMZ file from *df* and write it to *output_path*.

    Parameters
    ----------
    df : pandas.DataFrame
        Must contain at least ``timestamp``, ``lat`` and ``lon``.  
        When a ``mcg`` column is present it is used for colour coding.
    output_path : str | Path
        Target ``.kmz`` filename.
    name : str, default ``"impacts"``
        Layer name shown in Google Earth.
    center : (lat, lon) tuple, optional
        If provided, a purple push‑pin is added and Google Earth
        is instructed to zoom at ~20 km around that point.
    rayon_km : float, optional
        If given along with *center*, impacts farther than this radius (in km)
        are excluded from the KMZ.

    Returns
    -------
    Path
        The *output_path* as :class:`pathlib.Path`.
    """
    output_path = Path(output_path).with_suffix(".kmz")

    # ------------------------------------------------------------------ #
    # Build the KML document                                              #
    # ------------------------------------------------------------------ #

    # Optional geographic filter
    if rayon_km is not None:
        if center is None:
            raise ValueError("rayon_km specified but center is None")
        lat_c, lon_c = center
        df = df[
            df.apply(
                lambda r: _geo_dist_km(lat_c, lon_c, float(r["lat"]), float(r["lon"])) <= rayon_km,
                axis=1,
            )
        ]

    # ------------------------------------------------------------------
    # Compute global TimeSpan (min / max) to initialise Google Earth timeline
    # ------------------------------------------------------------------
    if not df.empty:
        ts_series = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
        begin_iso = ts_series.min().isoformat()
        end_iso = ts_series.max().isoformat()
    else:
        begin_iso = end_iso = datetime.now(timezone.utc).isoformat()

    kml_parts: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<kml xmlns="http://www.opengis.net/kml/2.2">',
        f"  <Document><name>{name}</name>",
    ]
    kml_parts.append(f"  <TimeSpan><begin>{begin_iso}</begin><end>{end_iso}</end></TimeSpan>")

    # Style definitions
    kml_parts.extend(
        _style_block(style_id, rgb) for style_id, rgb in _STYLE_RGB.items()
    )
    kml_parts.append(_center_style_block())

    # Optional LookAt (zoom) / centre marker
    if center:
        lat_c, lon_c = center
        kml_parts.append(
            f"""
    <LookAt>
      <longitude>{lon_c}</longitude>
      <latitude>{lat_c}</latitude>
      <altitude>0</altitude>
      <range>{20_000}</range> <!-- ~20 km -->
      <tilt>0</tilt><heading>0</heading>
      <altitudeMode>relativetoground</altitudeMode>
    </LookAt>
"""
        )
        kml_parts.append(
            f"""
    <Placemark>
      <name>centre</name>
      <styleUrl>#center</styleUrl>
      <Point><coordinates>{lon_c},{lat_c},0</coordinates></Point>
    </Placemark>
"""
        )

    # Iterate over impacts
    for _, row in df.iterrows():
        ts = row["timestamp"]
        if not isinstance(ts, datetime):
            ts = pd.to_datetime(ts, utc=True, errors="coerce")
        if ts is None or pd.isna(ts):
            ts = datetime.now(timezone.utc)
        ts_utc = ts.astimezone(timezone.utc)
        local_tz = get_localzone()
        ts_local = ts.astimezone(local_tz)

        lat = float(row["lat"])
        lon = float(row["lon"])
        mcg = row.get("mcg")
        style_id = _style_for_mcg(mcg)

        placemark = f"""
    <Placemark>
      <TimeStamp><when>{ts_utc.isoformat()}</when></TimeStamp>
      <styleUrl>#{style_id}</styleUrl>
      <description><![CDATA[
        <b>Date locale :</b> {ts_local.strftime('%d/%m/%Y %H:%M:%S')}<br/>
        <b>mcg :</b> {mcg if mcg is not None else 'NaN'}
      ]]></description>
      <Point><coordinates>{lon},{lat},0</coordinates></Point>
    </Placemark>
""".rstrip()
        kml_parts.append(placemark)

    # Close KML
    kml_parts.append("  </Document></kml>")
    kml_content = "\n".join(kml_parts)

    # ------------------------------------------------------------------ #
    # Write KML then compress as KMZ                                     #
    # ------------------------------------------------------------------ #
    tmp_kml = output_path.with_suffix(".kml")
    tmp_kml.write_text(kml_content, encoding="utf-8")

    try:
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as kmz:
            kmz.write(tmp_kml, arcname="doc.kml")
    finally:
        tmp_kml.unlink(missing_ok=True)
    return output_path
