import os
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from .config import Config
from .utils import parse_datetime, safe_numeric

# Constants
LARGE_FILE_THRESHOLD_MB = 1000
MARKETS_DTYPES = {
    "id": "string",
    "createdAt": "string",
    "closedTime": "string",
    "volume": "float64",
}
TRADES_DTYPES = {
    "market_id": "string",
    "timestamp": "string",
    "price": "float64",
    "usd_amount": "float64",
    "token_amount": "float64",
}
SNAPSHOTS_DTYPES = {
    "market_id": "string",
    "snapshot_ts": "string",
    "volume24hr": "float64",
    "volume1wk": "float64",
    "volume1mo": "float64",
    "volume1yr": "float64",
    "volume_total": "float64",
    "liquidity": "float64",
    "liquidityAmm": "float64",
    "liquidityClob": "float64",
    "openInterest": "float64",
    "lastTradePrice": "float64",
    "bestBid": "float64",
    "bestAsk": "float64",
    "spread": "float64",
    "score": "float64",
}


def _file_size_mb(path: str) -> float:
    return os.path.getsize(path) / (1024 * 1024) if os.path.exists(path) else 0.0


def _read_csv_chunked(path: str, dtypes: dict, chunk_size: int) -> pd.DataFrame:
    """Read CSV with chunking if file is large."""
    if _file_size_mb(path) > LARGE_FILE_THRESHOLD_MB:
        chunks = []
        for chunk in tqdm(
            pd.read_csv(path, dtype=dtypes, chunksize=chunk_size, low_memory=False, on_bad_lines="warn"),
            desc=f"Reading {Path(path).name}",
        ):
            chunks.append(chunk)
        # Use more efficient concatenation: concatenate in batches to reduce memory overhead
        if len(chunks) > 100:
            # For very large files, concatenate in batches
            batch_size = 50
            batched_chunks = []
            for i in range(0, len(chunks), batch_size):
                batch = chunks[i : i + batch_size]
                batched_chunks.append(pd.concat(batch, ignore_index=True))
            return pd.concat(batched_chunks, ignore_index=True)
        else:
            return pd.concat(chunks, ignore_index=True)
    return pd.read_csv(path, dtype=dtypes, low_memory=False, on_bad_lines="warn")


def _load_from_dataset_folder(cfg: Config, chunk_size: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load data from dataset folder."""
    markets_path = os.path.join(cfg.dataset_dir, "markets.csv")
    trades_path = os.path.join(cfg.processed_dir, "trades.csv")
    orderfilled_path = os.path.join(cfg.dataset_dir, "goldsky", "orderFilled.csv")

    print(f"Loading from dataset folder (markets.csv: {_file_size_mb(markets_path):.1f}MB)...")
    # Load markets
    markets_df = _read_csv_chunked(markets_path, MARKETS_DTYPES, chunk_size)
    print(f"  Loaded {len(markets_df):,} markets")
    markets_df = parse_datetime(markets_df, ["createdAt", "closedTime"])
    markets_df = safe_numeric(markets_df, ["volume"])
    markets_df["market_lifetime_hours"] = (
        markets_df["closedTime"] - markets_df["createdAt"]
    ).dt.total_seconds() / 3600.0

    # Create markets_static
    markets_static = pd.DataFrame(
        {
            "market_id": markets_df["id"].astype(str),
            "created_at": markets_df["createdAt"],
            "end_date": markets_df["closedTime"],
            "question": markets_df.get("question", ""),
            "market_slug": markets_df.get("market_slug", markets_df["id"].astype(str)),
            "final_volume_total": markets_df["volume"],
            "market_lifetime_hours": markets_df["market_lifetime_hours"],
            "event_id": None,
            "event_slug": None,
            "event_title": markets_df.get("question", ""),
            "market_title": markets_df.get("question", ""),
            "category": None,
            "subcategory": None,
        }
    )

    # Empty snapshots for dataset folder mode
    markets_snapshots = pd.DataFrame(
        columns=[
            "snapshot_ts",
            "market_id",
            "volume_total",
            "liquidity",
            "liquidityAmm",
            "liquidityClob",
            "openInterest",
            "lastTradePrice",
            "bestBid",
            "bestAsk",
            "spread",
            "volume24hr",
            "volume1wk",
            "volume1mo",
            "score",
        ]
    )

    # Return trade file paths for incremental processing (to avoid loading 69GB into memory)
    # Note: orderFilled.csv is RAW data from Goldsky subgraph that needs processing first.
    # It doesn't have market_id, so we only use processed/trades.csv which has been
    # converted from orderFilled.csv using the poly_data processing pipeline.
    # See: https://github.com/warproxxx/poly_data for processing details.

    trades_total_size_mb = 0
    trade_paths = []
    trade_dtypes = []

    # Only use processed trades.csv (skip raw orderFilled.csv)
    if os.path.exists(trades_path) and os.path.getsize(trades_path) > 0:
        file_size_mb = _file_size_mb(trades_path)
        trades_total_size_mb += file_size_mb
        trade_paths.append(trades_path)
        trade_dtypes.append(TRADES_DTYPES)
        print(f"  Found processed trades.csv ({file_size_mb:.1f}MB)")

    # Check orderFilled.csv exists but don't use it (informational only)
    if os.path.exists(orderfilled_path) and os.path.getsize(orderfilled_path) > 0:
        orderfilled_size_mb = _file_size_mb(orderfilled_path)
        print(
            f"  Note: orderFilled.csv exists ({orderfilled_size_mb:.1f}MB) but will be skipped (raw data, needs processing)"
        )

    if trades_total_size_mb > 5000:  # If total > 5GB, use incremental processing
        print(f"  Trade files total {trades_total_size_mb:.1f}MB - will process incrementally")
        # Return None as signal to use incremental processing, along with paths
        trades = None
        trades_info = {"paths": trade_paths, "dtypes": trade_dtypes}
    else:
        # For smaller files, load normally
        trades_list = []
        for path, dtypes in zip(trade_paths, trade_dtypes, strict=True):
            trades_df = _read_csv_chunked(path, dtypes, chunk_size)
            if len(trades_df) > 0:
                trades_list.append(trades_df)

        trades = (
            pd.concat(trades_list, ignore_index=True)
            if trades_list
            else pd.DataFrame(
                columns=["market_id", "timestamp", "price", "usd_amount", "token_amount", "transactionHash"]
            )
        )
        print(f"  Loaded {len(trades):,} trades")
        trades_info = None

    return markets_static, markets_snapshots, trades, trades_info


def load_data(
    cfg: Config, chunk_size: int | None = None
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame | None, dict | None]:
    """Load data from either dataset folder or collected data folder.

    Returns:
        markets_static, markets_snapshots, trades, trades_info
        - trades: DataFrame if loaded, None if incremental processing needed
        - trades_info: dict with 'paths' and 'dtypes' if incremental processing needed, None otherwise
    """
    if chunk_size is None:
        chunk_size = cfg.chunk_size
    if cfg.use_dataset_folder:
        return _load_from_dataset_folder(cfg, chunk_size)

    # Load collected data
    static_path = os.path.join(cfg.data_dir, "markets_static.csv")
    snapshots_path = os.path.join(cfg.data_dir, "markets_snapshots.csv")

    print(
        f"Loading collected data (static: {_file_size_mb(static_path):.1f}MB, snapshots: {_file_size_mb(snapshots_path):.1f}MB)..."
    )
    markets_static = pd.read_csv(static_path, dtype={"market_id": "string"}, low_memory=False, on_bad_lines="warn")
    markets_snapshots = _read_csv_chunked(snapshots_path, SNAPSHOTS_DTYPES, chunk_size)
    print(f"  Loaded {len(markets_static):,} markets, {len(markets_snapshots):,} snapshots")

    # Preprocess
    markets_static = parse_datetime(markets_static, ["created_at", "end_date"])
    markets_snapshots = parse_datetime(markets_snapshots, ["snapshot_ts"])
    markets_snapshots = safe_numeric(
        markets_snapshots,
        [
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
            "score",
        ],
    )
    markets_static["market_lifetime_hours"] = (
        markets_static["end_date"] - markets_static["created_at"]
    ).dt.total_seconds() / 3600.0

    trades = pd.DataFrame(columns=["market_id", "timestamp", "price", "usd_amount", "token_amount", "transactionHash"])

    return markets_static, markets_snapshots, trades, None


def load_markets_static_only(cfg: Config) -> pd.DataFrame:
    """Load only markets_static data (optimized for embeddings generation, skips trades and snapshots)."""
    if cfg.use_dataset_folder:
        markets_path = os.path.join(cfg.dataset_dir, "markets.csv")
        print(f"Loading markets data (markets.csv: {_file_size_mb(markets_path):.1f}MB)...")
        markets_df = _read_csv_chunked(markets_path, MARKETS_DTYPES, cfg.chunk_size)
        print(f"  Loaded {len(markets_df):,} markets")
        markets_df = parse_datetime(markets_df, ["createdAt", "closedTime"])
        markets_df = safe_numeric(markets_df, ["volume"])
        markets_df["market_lifetime_hours"] = (
            markets_df["closedTime"] - markets_df["createdAt"]
        ).dt.total_seconds() / 3600.0

        markets_static = pd.DataFrame(
            {
                "market_id": markets_df["id"].astype(str),
                "created_at": markets_df["createdAt"],
                "end_date": markets_df["closedTime"],
                "question": markets_df.get("question", ""),
                "market_slug": markets_df.get("market_slug", markets_df["id"].astype(str)),
                "final_volume_total": markets_df["volume"],
                "market_lifetime_hours": markets_df["market_lifetime_hours"],
                "event_id": None,
                "event_slug": None,
                "event_title": markets_df.get("question", ""),
                "market_title": markets_df.get("question", ""),
                "category": None,
                "subcategory": None,
            }
        )
        return markets_static
    else:
        # Load collected data - only markets_static
        static_path = os.path.join(cfg.data_dir, "markets_static.csv")
        print(f"Loading markets data (markets_static.csv: {_file_size_mb(static_path):.1f}MB)...")
        markets_static = pd.read_csv(static_path, dtype={"market_id": "string"}, low_memory=False, on_bad_lines="warn")
        print(f"  Loaded {len(markets_static):,} markets")
        markets_static = parse_datetime(markets_static, ["created_at", "end_date"])
        markets_static["market_lifetime_hours"] = (
            markets_static["end_date"] - markets_static["created_at"]
        ).dt.total_seconds() / 3600.0
        return markets_static
