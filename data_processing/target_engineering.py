import pandas as pd

from .config import Config


def create_target(markets_snapshots: pd.DataFrame, markets_static: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """Create binary target based on volume threshold."""
    if len(markets_snapshots) == 0 or "volume_total" not in markets_snapshots.columns:
        final_volume = markets_static[["market_id", "final_volume_total"]].copy()
    else:
        snapshots_sorted = markets_snapshots.sort_values(["market_id", "snapshot_ts"])
        final_snapshot = snapshots_sorted.groupby("market_id", sort=False).tail(1)
        final_volume = final_snapshot[["market_id", "volume_total"]].rename(
            columns={"volume_total": "final_volume_total"}
        )

    if cfg.target_volume_threshold is not None:
        threshold = cfg.target_volume_threshold
        print(f"  Using fixed threshold: {threshold:,.0f}")
    else:
        threshold = final_volume["final_volume_total"].quantile(cfg.target_volume_percentile / 100.0)
        print(f"  Using {cfg.target_volume_percentile}th percentile threshold: {threshold:,.0f}")

    final_volume["target_high_volume"] = (final_volume["final_volume_total"] >= threshold).astype(int)
    positive_count = final_volume["target_high_volume"].sum()
    print(
        f"  Target distribution: {positive_count:,}/{len(final_volume):,} ({100 * positive_count / len(final_volume):.1f}%) positive"
    )

    return final_volume
