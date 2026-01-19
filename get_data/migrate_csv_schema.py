# file: migrate_csv_schema.py

import os
from typing import List

import pandas as pd


DATA_DIR = "data"
STATIC_PATH = os.path.join(DATA_DIR, "markets_static.csv")
SNAPSHOT_PATH = os.path.join(DATA_DIR, "markets_snapshots.csv")

# Docelowe schematy – muszą być spójne z aktualnym kodem collectora
STATIC_FIELDS: List[str] = [
    "market_id",
    "event_id",
    "event_slug",
    "event_title",
    "event_subtitle",
    "event_description",
    "market_slug",
    "market_title",
    "market_subtitle",
    "question",
    "category",
    "subcategory",
    "created_at",
    "end_date",
    "resolution_source",
    "resolved_by",
    "final_volume_total",
    "final_volume24hr",
    "tags",
    "mailchimp_tag",
    "promotion_group",
    "commentCount",
]

SNAPSHOT_FIELDS: List[str] = [
    "snapshot_ts",
    "market_id",
    "active",
    "closed",
    "featured",
    "new",
    "archived",
    "restricted",
    "volume24hr",
    "volume1wk",
    "volume1mo",
    "volume1yr",
    "volume_total",
    "liquidity",
    "liquidityAmm",
    "liquidityClob",
    "openInterest",
    "lastTradePrice",
    "bestBid",
    "bestAsk",
    "spread",
    "oneDayPriceChange",
    "oneWeekPriceChange",
    "commentCount",
    "competitive",
    "score",
    "mailchimp_tag",
    "promotion_group",
]


def _safe_read_csv(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        print(f"[WARN] File not found: {path}")
        return pd.DataFrame()
    try:
        df = pd.read_csv(path, dtype=str)  # wszystko jako string, żeby nic nie zgubić
        return df
    except Exception as e:
        print(f"[ERROR] Failed to read {path}: {e}")
        return pd.DataFrame()


def _ensure_columns(df: pd.DataFrame, target_cols: List[str]) -> pd.DataFrame:
    """
    Upewnia się, że DataFrame ma wszystkie kolumny z target_cols.
    - Istniejące kolumny są zachowane.
    - Brakujące są dodawane jako puste stringi.
    - Kolumny są ułożone w kolejności target_cols.
    """
    if df.empty:
        # Jeśli plik był pusty lub nie istniał – utwórz pusty DF z nagłówkami
        return pd.DataFrame(columns=target_cols)

    for col in target_cols:
        if col not in df.columns:
            df[col] = ""  # brakujące dane wypełniamy pustym stringiem

    # Możemy zachować też stare kolumny „extra”, ale w większości przypadków
    # chcemy tylko target_cols – tu zostawiamy tylko target_cols.
    df = df[target_cols]
    return df


def _convert_numeric_columns(df: pd.DataFrame, numeric_cols: List[str]) -> pd.DataFrame:
    """
    Próbuje skonwertować wybrane kolumny do typu numerycznego (float),
    nie krusząc się na błędach – nieparsowalne wartości zostają jako NaN.
    Następnie zamienia NaN na pusty string, żeby pozostać kompatybilnym z podejściem „string w CSV”.
    """
    if df.empty:
        return df

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            # W CSV nadal chcemy stringi, ale z „ładnie” zapisanymi liczbami
            df[col] = df[col].apply(lambda x: "" if pd.isna(x) else str(x))

    return df


def migrate_static_csv() -> None:
    df_static = _safe_read_csv(STATIC_PATH)

    # Mapowanie starych nazw na nowe (jeśli zmieniłeś nazwy kolumn w międzyczasie)
    rename_map = {
        # np. jeśli wcześniej nie miałeś market_title i używałeś question jako title:
        # "question": "question"  # tu nie trzeba nic zmieniać, przykład zostawiony jako placeholder
    }

    if not df_static.empty and rename_map:
        df_static = df_static.rename(columns=rename_map)

    df_static = _ensure_columns(df_static, STATIC_FIELDS)

    # Dla static zwykle nie trzeba castować do numeric, bo to meta.
    # Ale jeśli chcesz, możesz dodać np.:
    # df_static = _convert_numeric_columns(df_static, ["final_volume_total", "final_volume24hr"])

    backup_path = STATIC_PATH.replace(".csv", ".bak.csv")
    os.replace(STATIC_PATH, backup_path)
    print(f"[INFO] Backup static CSV -> {backup_path}")

    df_static.to_csv(STATIC_PATH, index=False)
    print(f"[INFO] Migrated static CSV saved -> {STATIC_PATH}")


def migrate_snapshot_csv() -> None:
    df_snap = _safe_read_csv(SNAPSHOT_PATH)

    rename_map = {
        # jeśli w starym pliku nazwy różniły się od aktualnych SNAPSHOT_FIELDS,
        # możesz dopisać mapowanie tutaj, np.:
        # "liquidityNum": "liquidity",
    }

    if not df_snap.empty and rename_map:
        df_snap = df_snap.rename(columns=rename_map)

    df_snap = _ensure_columns(df_snap, SNAPSHOT_FIELDS)

    # Spróbujemy doprowadzić pola volume/liquidity/ceny do „ładnych” liczb (stringów z liczbą)
    numeric_like_cols = [
        "volume24hr",
        "volume1wk",
        "volume1mo",
        "volume1yr",
        "volume_total",
        "liquidity",
        "liquidityAmm",
        "liquidityClob",
        "openInterest",
        "lastTradePrice",
        "bestBid",
        "bestAsk",
        "spread",
        "oneDayPriceChange",
        "oneWeekPriceChange",
        "competitive",
        "score",
    ]
    df_snap = _convert_numeric_columns(df_snap, numeric_like_cols)

    backup_path = SNAPSHOT_PATH.replace(".csv", ".bak.csv")
    os.replace(SNAPSHOT_PATH, backup_path)
    print(f"[INFO] Backup snapshot CSV -> {backup_path}")

    df_snap.to_csv(SNAPSHOT_PATH, index=False)
    print(f"[INFO] Migrated snapshot CSV saved -> {SNAPSHOT_PATH}")


if __name__ == "__main__":
    os.makedirs(DATA_DIR, exist_ok=True)
    migrate_static_csv()
    migrate_snapshot_csv()
