"""
Paquet principal *lightningviewer*.

On ré-exporte ici les fonctions publiques pour permettre :

    >>> import lightningviewer as lv
    >>> lv.download_range(...)
"""

from __future__ import annotations

__version__ = "0.7.1"

import importlib
import pathlib
import sys
import types
from dotenv import load_dotenv

from ._paths import ENV_FILE

# Charge automatiquement les variables d'environnement depuis .env
load_dotenv(str(ENV_FILE))

# Racine du projet (utile à d’autres modules)
ROOT = pathlib.Path(__file__).resolve().parent.parent


def _lazy_import(mod_name: str) -> types.ModuleType:
    """
    Import différé d’un sous-module du paquet.

    Exemple :
        parse = _lazy_import("parser").parse
    """
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    return importlib.import_module(f"{__name__}.{mod_name}")


# ---------------------------------------------------------------------------
# API ré-exportée
# ---------------------------------------------------------------------------
from .api import (  # noqa: E402  – import tardif voulu
    download_range,
    query_impacts,
    build_kmz,
    purge_old,
)

__all__ = [
    "download_range",
    "query_impacts",
    "build_kmz",
    "purge_old",
    "__version__",
]
