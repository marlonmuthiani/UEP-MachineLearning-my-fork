from dataclasses import dataclass


@dataclass
class Config:
    data_dir: str = "data"
    dataset_dir: str = "dataset"
    processed_dir: str = "dataset/processed"
    modeling_dir: str = "dataset/modeling"

    use_dataset_folder: bool = False

    target_volume_threshold: float | None = None
    target_volume_percentile: float | None = 75.0

    snapshot_horizon_hours: float = 24.0
    snapshot_age_tolerance_hours: float = 6.0
    min_snapshots_per_market: int = 1

    outlier_z_threshold: float = 8.0

    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = 384

    chunk_size: int = 1_000_000  # Increased from 100k to 1M for better performance on large files
