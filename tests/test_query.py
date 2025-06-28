import pandas as pd
from datetime import datetime
from lightningviewer.blitz_query import requete_impacts

def test_requete_impacts_returns_dataframe():
    """
    Vérifie que requete_impacts renvoie bien un pandas.DataFrame
    et que la structure des colonnes attendues est présente.
    """
    # période d’intérêt réduite pour test
    start = datetime(2024, 6, 1, 0, 0)
    end = datetime(2024, 6, 1, 0, 10)
    df = requete_impacts(start, end)

    # Type et colonnes
    assert isinstance(df, pd.DataFrame)
    expected_cols = {"timestamp", "lat", "lon", "mcg"}
    assert expected_cols.issubset(df.columns), f"Colonnes manquantes : {expected_cols - set(df.columns)}"
