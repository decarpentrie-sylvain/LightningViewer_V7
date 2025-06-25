"""
lightningviewer._paths
----------------------

Central place where every module can obtain **absolute paths** to the
project‐level directories (root, data/, archives/, …) without repeating
the same logic everywhere.

Nothing here touches the network or the database; only `pathlib` is used.
"""

from __future__ import annotations

import os
import pathlib


# ────────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────────
def _project_root() -> pathlib.Path:
    """
    Return the absolute *project* root.

    We assume the following layout (editable or wheel install):

        project_root/
        ├─ src/
        │   └─ lightningviewer/
        │       ├─ __init__.py
        │       └─ _paths.py   ← *this* file
        ├─ data/
        ├─ README.md
        └─ .env

    i.e. `_paths.py` is always at
        project_root / "src" / "lightningviewer" / "_paths.py"
    so we go three parents up.
    """
    return pathlib.Path(__file__).resolve().parents[2]


# ────────────────────────────────────────────────────────────────────────────────
# Public constants
# ────────────────────────────────────────────────────────────────────────────────
ROOT: pathlib.Path = _project_root()

DATA_DIR: pathlib.Path = ROOT / "data"
ARCHIVES_DIR: pathlib.Path = DATA_DIR / "archives"
LOG_DIR: pathlib.Path = pathlib.Path.home() / "Library" / "Logs" / "LightningViewer"


DB_PATH: pathlib.Path = DATA_DIR / "blitz.db"
ENV_FILE: pathlib.Path = ROOT / ".env"

# path for the latest generated KMZ
KMZ_PATH: pathlib.Path = ROOT / "impacts.kmz"

# ensure mandatory directories always exist when the module is imported
for _d in (DATA_DIR, ARCHIVES_DIR, LOG_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# convenience: project‐relative path factory
def rel(*parts: str | os.PathLike) -> pathlib.Path:  # noqa: D401
    """shorthand: `rel("subdir", "file.txt")` → ROOT / "subdir" / "file.txt"."""
    return ROOT.joinpath(*parts)


__all__ = [
    "ROOT",
    "DATA_DIR",
    "ARCHIVES_DIR",
    "LOG_DIR",
    "DB_PATH",
    "ENV_FILE",
    "KMZ_PATH",
    "rel",
]
