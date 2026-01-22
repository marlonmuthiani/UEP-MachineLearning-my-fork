import numpy as np
import pandas as pd

from .config import Config
from .utils import fill_na_numeric

# Constants
SNAPSHOT_FEATURES = [
    "market_id",
    "snapshot_ts",
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
    "volume_total",
    "score",
]
NUMERIC_SNAPSHOT_COLS = [
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
    "volume_total",
    "score",
]
TRADE_AGG_COLS = [
    "trade_count_0_24h",
    "usd_vol_0_24h",
    "token_vol_0_24h",
    "price_mean_0_24h",
    "price_std_0_24h",
]


def get_snapshot_at_horizon(markets_snapshots: pd.DataFrame, markets_static: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """Get snapshot closest to horizon time for each market."""
    if len(markets_snapshots) == 0:
        # Create placeholder snapshots with timezone-aware timestamps
        snapshot_ts = markets_static["created_at"] + pd.Timedelta(hours=cfg.snapshot_horizon_hours)
        # Ensure timezone consistency
        if markets_static["created_at"].dt.tz is not None and snapshot_ts.dt.tz is None:
            snapshot_ts = snapshot_ts.dt.tz_localize("UTC")

        snap_horizon = pd.DataFrame(
            {
                "market_id": markets_static["market_id"].values,
                "snapshot_ts": snapshot_ts.values,
            }
        )
        for col in NUMERIC_SNAPSHOT_COLS:
            snap_horizon[col] = 0.0
        print(f"  Created placeholder snapshots for {len(snap_horizon):,} markets")
        return snap_horizon

    snapshots_sorted = markets_snapshots.sort_values(["market_id", "snapshot_ts"])
    market_created_dict = markets_static.set_index("market_id")["created_at"].to_dict()
    snapshots_sorted["created_at"] = snapshots_sorted["market_id"].map(market_created_dict)
    snapshots_sorted["age_hours"] = (
        snapshots_sorted["snapshot_ts"] - snapshots_sorted["created_at"]
    ).dt.total_seconds() / 3600.0

    target_age = cfg.snapshot_horizon_hours
    max_age_diff = cfg.snapshot_age_tolerance_hours
    snapshots_sorted["age_diff"] = (snapshots_sorted["age_hours"] - target_age).abs()

    mask = (snapshots_sorted["age_hours"] >= 0) & (snapshots_sorted["age_hours"] <= target_age + max_age_diff)
    snap_candidate = (
        snapshots_sorted[mask].sort_values(["market_id", "age_diff"]).groupby("market_id", sort=False).head(1)
    )

    missing_markets = set(markets_static["market_id"]) - set(snap_candidate["market_id"])
    if missing_markets:
        first_snap = (
            snapshots_sorted[snapshots_sorted["market_id"].isin(missing_markets)]
            .groupby("market_id", sort=False)
            .head(1)
        )
        snap_horizon = pd.concat([snap_candidate, first_snap], ignore_index=True)
    else:
        snap_horizon = snap_candidate.copy()

    print(f"  Found snapshots for {len(snap_horizon):,} markets")
    return snap_horizon


def aggregate_trades_0_24h(trades: pd.DataFrame, markets_static: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """Aggregate trades within first 24h window."""
    if len(trades) == 0:
        print("  No trades to aggregate")
        return pd.DataFrame({col: [] for col in ["market_id"] + TRADE_AGG_COLS})

    market_created_dict = markets_static.set_index("market_id")["created_at"].to_dict()
    trades["created_at"] = trades["market_id"].map(market_created_dict)
    trades["age_hours"] = (trades["timestamp"] - trades["created_at"]).dt.total_seconds() / 3600.0

    trades_0_24h = trades[(trades["age_hours"] >= 0) & (trades["age_hours"] <= cfg.snapshot_horizon_hours)]
    print(f"  Filtered {len(trades_0_24h):,} trades within {cfg.snapshot_horizon_hours}h window")

    trade_aggs = (
        trades_0_24h.groupby("market_id", sort=False)
        .agg(
            trade_count_0_24h=("transactionHash", "nunique"),
            usd_vol_0_24h=("usd_amount", "sum"),
            token_vol_0_24h=("token_amount", "sum"),
            price_mean_0_24h=("price", "mean"),
            price_std_0_24h=("price", "std"),
        )
        .reset_index()
    )

    print(f"  Aggregated trades for {len(trade_aggs):,} markets")
    return trade_aggs


def aggregate_trades_incremental(
    trades_paths: list[str], markets_static: pd.DataFrame, cfg: Config, chunk_size: int, dtypes_list: list[dict]
) -> pd.DataFrame:
    """Aggregate trades incrementally from files without loading everything into memory."""
    import os

    from tqdm import tqdm

    from .utils import parse_datetime

    market_created_dict = markets_static.set_index("market_id")["created_at"].to_dict()

    # Initialize aggregation dictionaries
    market_stats = {}  # market_id -> {counts: set, sums: dict, prices: list}

    total_rows = 0
    filtered_rows = 0

    for path, dtypes in zip(trades_paths, dtypes_list, strict=True):
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            continue

        file_name = os.path.basename(path)

        # Check file schema first by reading just the header
        try:
            sample = pd.read_csv(path, nrows=1, dtype=dtypes, low_memory=False, on_bad_lines="warn")
            required_cols = ["market_id", "timestamp", "transactionHash"]
            if not all(col in sample.columns for col in required_cols):
                print(f"  Skipping {file_name} - missing required columns (has: {list(sample.columns)})")
                continue
        except Exception as e:
            print(f"  Skipping {file_name} - error reading header: {e}")
            continue

        print(f"  Processing {file_name}...")

        for chunk in tqdm(
            pd.read_csv(path, dtype=dtypes, chunksize=chunk_size, low_memory=False, on_bad_lines="warn"),
            desc=f"  Reading {file_name}",
        ):
            if len(chunk) == 0:
                continue

            total_rows += len(chunk)

            # Parse timestamp if needed
            if "timestamp" in chunk.columns:
                chunk = parse_datetime(chunk, ["timestamp"])

            # Map market creation times
            chunk["created_at"] = chunk["market_id"].map(market_created_dict)
            chunk = chunk[chunk["created_at"].notna()]  # Only keep trades for markets we know about

            if len(chunk) == 0:
                continue

            # Calculate age
            chunk["age_hours"] = (chunk["timestamp"] - chunk["created_at"]).dt.total_seconds() / 3600.0

            # Filter to 24h window
            trades_0_24h = chunk[(chunk["age_hours"] >= 0) & (chunk["age_hours"] <= cfg.snapshot_horizon_hours)]
            filtered_rows += len(trades_0_24h)

            if len(trades_0_24h) == 0:
                continue

            # Aggregate incrementally
            for market_id, group in trades_0_24h.groupby("market_id"):
                if market_id not in market_stats:
                    market_stats[market_id] = {
                        "transaction_hashes": set(),
                        "usd_vol": 0.0,
                        "token_vol": 0.0,
                        "prices": [],
                    }

                stats = market_stats[market_id]
                if "transactionHash" in group.columns:
                    stats["transaction_hashes"].update(group["transactionHash"].dropna().unique())
                if "usd_amount" in group.columns:
                    stats["usd_vol"] += group["usd_amount"].sum()
                if "token_amount" in group.columns:
                    stats["token_vol"] += group["token_amount"].sum()
                if "price" in group.columns:
                    stats["prices"].extend(group["price"].dropna().tolist())

    print(
        f"  Processed {total_rows:,} total trades, filtered to {filtered_rows:,} within {cfg.snapshot_horizon_hours}h window"
    )

    if not market_stats:
        print("  No trades to aggregate")
        return pd.DataFrame({col: [] for col in ["market_id"] + TRADE_AGG_COLS})

    # Convert to final DataFrame
    results = []
    for market_id, stats in market_stats.items():
        prices = stats["prices"]
        results.append(
            {
                "market_id": market_id,
                "trade_count_0_24h": len(stats["transaction_hashes"]),
                "usd_vol_0_24h": stats["usd_vol"],
                "token_vol_0_24h": stats["token_vol"],
                "price_mean_0_24h": np.mean(prices) if prices else 0.0,
                "price_std_0_24h": np.std(prices) if len(prices) > 1 else 0.0,
            }
        )

    trade_aggs = pd.DataFrame(results)
    print(f"  Aggregated trades for {len(trade_aggs):,} markets")
    return trade_aggs


def build_snapshot_features(snap_horizon: pd.DataFrame) -> pd.DataFrame:
    """Build features from snapshot data."""
    snap_feat = snap_horizon[SNAPSHOT_FEATURES].copy()
    snap_feat = fill_na_numeric(snap_feat, NUMERIC_SNAPSHOT_COLS, value=0.0)

    # Derived features
    snap_feat["mid_price_24h"] = (
        ((snap_feat["bestBid"] + snap_feat["bestAsk"]) / 2.0).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    )
    snap_feat["spread_pct_24h"] = np.where(
        snap_feat["mid_price_24h"] > 0, snap_feat["spread"] / snap_feat["mid_price_24h"], 0.0
    )
    snap_feat["liquidity_per_vol24h"] = np.where(
        snap_feat["volume24hr"] > 0, snap_feat["liquidity"] / snap_feat["volume24hr"], 0.0
    )

    return snap_feat


def build_static_features(markets_static: pd.DataFrame, snap_feat: pd.DataFrame) -> pd.DataFrame:
    """Build static market features."""
    static_features = markets_static[
        [
            "market_id",
            "event_id",
            "event_slug",
            "market_slug",
            "category",
            "subcategory",
            "created_at",
            "end_date",
            "market_lifetime_hours",
        ]
    ].copy()

    static_features = static_features.merge(snap_feat[["market_id", "snapshot_ts"]], on="market_id", how="left")

    # Ensure timezone consistency for datetime subtraction
    if static_features["end_date"].dt.tz is not None:
        # If end_date is tz-aware, ensure snapshot_ts is also tz-aware
        if static_features["snapshot_ts"].dt.tz is None:
            static_features["snapshot_ts"] = static_features["snapshot_ts"].dt.tz_localize("UTC")
    elif static_features["snapshot_ts"].dt.tz is not None:
        # If snapshot_ts is tz-aware but end_date is not, make end_date tz-aware
        static_features["end_date"] = static_features["end_date"].dt.tz_localize("UTC")

    static_features["time_to_end_hours_at_24h"] = (
        static_features["end_date"] - static_features["snapshot_ts"]
    ).dt.total_seconds() / 3600.0

    return static_features


def assemble_dataset(
    static_features: pd.DataFrame,
    snap_feat: pd.DataFrame,
    trade_aggs: pd.DataFrame,
    final_volume: pd.DataFrame,
    cfg: Config,
) -> pd.DataFrame:
    """Assemble final dataset from all feature sources."""
    dataset = static_features.merge(snap_feat, on="market_id", how="left", suffixes=("", "_snap"))
    dataset = dataset.merge(trade_aggs, on="market_id", how="left")
    dataset = dataset.merge(
        final_volume[["market_id", "final_volume_total", "target_high_volume"]], on="market_id", how="left"
    )
    dataset = fill_na_numeric(dataset, TRADE_AGG_COLS, value=0.0)

    print(f"  Assembled dataset: {len(dataset):,} rows × {len(dataset.columns)} columns")
    return dataset
