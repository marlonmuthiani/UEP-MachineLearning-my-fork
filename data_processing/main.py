import os

import numpy as np
import pandas as pd

from .config import Config
from .data_loader import load_data
from .feature_engineering import (
    aggregate_trades_0_24h,
    aggregate_trades_incremental,
    assemble_dataset,
    build_snapshot_features,
    build_static_features,
    get_snapshot_at_horizon,
)
from .target_engineering import create_target
from .utils import remove_extreme_outliers


def load_embeddings(cfg: Config, use_dataset_folder: bool = False) -> pd.DataFrame | None:
    """Load embeddings from file if available."""
    data_source_suffix = "_dataset" if use_dataset_folder else "_collected"
    embeddings_path = os.path.join(cfg.modeling_dir, f"text_embeddings{data_source_suffix}.csv")

    if not os.path.exists(embeddings_path):
        fallback_path = os.path.join(cfg.modeling_dir, "text_embeddings.csv")
        if os.path.exists(fallback_path):
            embeddings_path = fallback_path
        else:
            return None

    embeddings = pd.read_csv(embeddings_path, dtype={"market_id": "string"})
    return embeddings


def main(include_embeddings: bool = False, use_dataset_folder: bool = False):
    """Main processing pipeline."""
    print("\n" + "=" * 60)
    print("MARKET DATA PROCESSING PIPELINE")
    print(f"Data source: {'dataset folder' if use_dataset_folder else 'collected data'}")
    print("=" * 60 + "\n")

    cfg = Config()
    cfg.use_dataset_folder = use_dataset_folder
    os.makedirs(cfg.modeling_dir, exist_ok=True)

    print("[1/7] Loading data...")
    markets_static, markets_snapshots, trades, trades_info = load_data(cfg)

    print("\n[2/7] Creating target variable...")
    final_volume = create_target(markets_snapshots, markets_static, cfg)

    print("\n[3/7] Getting snapshot at horizon...")
    snap_horizon = get_snapshot_at_horizon(markets_snapshots, markets_static, cfg)
    del markets_snapshots

    print("\n[4/7] Aggregating trades...")
    if trades_info is not None:
        # Use incremental aggregation for large files
        trade_aggs = aggregate_trades_incremental(
            trades_info["paths"], markets_static, cfg, cfg.chunk_size, trades_info["dtypes"]
        )
    else:
        # Use standard aggregation for smaller files
        trade_aggs = aggregate_trades_0_24h(trades, markets_static, cfg)
        del trades

    print("\n[5/7] Building features...")
    snap_feat = build_snapshot_features(snap_horizon)
    static_feat = build_static_features(markets_static, snap_feat)

    print("\n[6/7] Assembling dataset...")
    dataset = assemble_dataset(static_feat, snap_feat, trade_aggs, final_volume, cfg)

    embeddings_loaded = False
    if include_embeddings:
        print("\n[6.5/7] Loading embeddings...")
        embeddings = load_embeddings(cfg, use_dataset_folder)
        if embeddings is not None:
            dataset["market_id"] = dataset["market_id"].astype(str)
            embeddings["market_id"] = embeddings["market_id"].astype(str)
            dataset = dataset.merge(embeddings, on="market_id", how="left")
            embeddings_loaded = True
            print(f"  Loaded {embeddings.shape[1] - 1} embedding columns")
        else:
            print("  Warning: Embeddings file not found, skipping")

    print("\n[7/7] Post-processing...")
    numeric_cols = dataset.select_dtypes(include=[np.number]).columns.tolist()
    before_count = len(dataset)
    dataset = remove_extreme_outliers(dataset, numeric_cols, z_thresh=cfg.outlier_z_threshold)
    after_count = len(dataset)
    if before_count != after_count:
        print(f"  Removed {before_count - after_count:,} outlier rows")

    before_count = len(dataset)
    dataset = dataset[~dataset["final_volume_total"].isna()].copy()
    after_count = len(dataset)
    if before_count != after_count:
        print(f"  Removed {before_count - after_count:,} rows with missing targets")

    # Save
    threshold_str = (
        f"{cfg.target_volume_threshold:.0f}" if cfg.target_volume_threshold else f"p{cfg.target_volume_percentile:.0f}"
    )
    data_source_suffix = "_dataset" if use_dataset_folder else "_collected"
    embeddings_suffix = "_with_embeddings" if embeddings_loaded else ""
    output_path = os.path.join(
        cfg.modeling_dir, f"markets_ml_{threshold_str}{data_source_suffix}{embeddings_suffix}.csv"
    )

    print(f"\nSaving dataset to: {output_path}")
    dataset.to_csv(output_path, index=False, chunksize=10000)

    print("\n" + "=" * 60)
    print("PROCESSING COMPLETE")
    print("=" * 60)
    print(f"Final dataset shape: {dataset.shape[0]:,} rows × {dataset.shape[1]} columns")
    print("\nTarget distribution:")
    target_counts = dataset["target_high_volume"].value_counts().sort_index()
    for val, count in target_counts.items():
        pct = 100 * count / len(dataset)
        label = "High Volume" if val == 1 else "Low Volume"
        print(f"  {label}: {count:,} ({pct:.1f}%)")

    return dataset


if __name__ == "__main__":
    import warnings

    warnings.filterwarnings("ignore", category=RuntimeWarning, module="runpy")
    main()
