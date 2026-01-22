import numpy as np
import pandas as pd


def parse_datetime(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Parse datetime columns."""
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)
    return df


def safe_numeric(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Convert columns to numeric safely."""
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def remove_extreme_outliers(df: pd.DataFrame, cols: list[str], z_thresh: float = 6.0) -> pd.DataFrame:
    """Remove outliers based on z-score threshold."""
    mask = pd.Series(True, index=df.index)
    for col in cols:
        if col not in df.columns:
            continue
        s = df[col]
        mean, std = s.mean(), s.std(ddof=0)
        if std == 0 or np.isnan(std):
            continue
        mask &= ((s - mean) / std).abs() < z_thresh
    return df[mask]


def fill_na_numeric(df: pd.DataFrame, cols: list[str], value: float = 0.0) -> pd.DataFrame:
    """Fill NaN values in numeric columns."""
    for col in cols:
        if col in df.columns:
            df[col] = df[col].fillna(value)
    return df
