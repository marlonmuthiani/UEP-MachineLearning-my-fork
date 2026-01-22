# Market Data Processing Pipeline

A modular data processing pipeline for preparing market prediction data for machine learning models.

## Features

- **Dual Data Sources**: Process data from collected sources (`data/`) or external dataset folder (`dataset/`)
- **Feature Engineering**: Extract features from market snapshots, trades, and static market data
- **Text Embeddings**: Generate embeddings from market questions and titles
- **Target Engineering**: Create binary targets based on volume thresholds (fixed or percentile-based)
- **Large File Support**: Optimized for handling large CSV files (35GB+) with chunked processing
- **Progress Tracking**: Detailed progress information throughout the pipeline

## Installation

```bash
uv sync
```

## Dataset Setup

To download and unpack the historical dataset:

```bash
curl -L https://polydata-archive.s3.us-east-1.amazonaws.com/archive.tar.xz | tar -xJf - -C dataset
```

This will stream the download directly to tar, avoiding intermediate disk writes and efficiently extracting to the `dataset` folder.

## Quick Start

### Basic Usage

**For Training (Historical Dataset):**
Use the external dataset folder for training models:
```bash
python -m data_processing.run --use-external-dataset
```
This processes data from `dataset/markets.csv` and `dataset/processed/trades.csv` (historical data).

**For Predictions (Current Data):**
Use collected data from the `data/` folder for making predictions:
```bash
python -m data_processing.run
```
This processes data from `data/markets_static.csv` and `data/markets_snapshots.csv` (current/live data).

### With Text Embeddings

Generate embeddings first:
```bash
python -m data_processing.embeddings
```

Then run pipeline with embeddings:
```bash
python -m data_processing.run --embeddings
python -m data_processing.run --use-external-dataset --embeddings
```

## Command Line Options

- `--embeddings`: Include text embeddings in the output dataset
- `--use-external-dataset`: Use data from `dataset/markets.csv` instead of collected data from `data/` folder

## Output Files

Output files are saved to `dataset/modeling/` with distinctive naming:

### Collected Data (default)
- `markets_ml_p75_collected.csv` - Standard dataset
- `markets_ml_p75_collected_with_embeddings.csv` - With text embeddings

### Dataset Folder
- `markets_ml_p75_dataset.csv` - Standard dataset
- `markets_ml_p75_dataset_with_embeddings.csv` - With text embeddings

The threshold (`p75`) indicates the percentile used for target creation (default: 75th percentile).

## Configuration

Edit `config.py` to customize:

- `target_volume_threshold`: Fixed volume threshold (e.g., 50000)
- `target_volume_percentile`: Percentile-based threshold (default: 75.0)
- `snapshot_horizon_hours`: Time horizon for snapshot selection (default: 24.0)
- `outlier_z_threshold`: Z-score threshold for outlier removal (default: 8.0)
- `embedding_model_name`: Sentence transformer model for embeddings
- `chunk_size`: Chunk size for large file processing (default: 100000)

## Data Structure

### Input Files

**Collected Data Mode** (`data/` folder):
- `markets_static.csv` - Static market information
- `markets_snapshots.csv` - Time-series snapshots of market states
- `dataset/processed/trades.csv` - Trade transaction data

**Dataset Folder Mode** (`dataset/` folder):
- `markets.csv` - External/pre-existing market dataset (from [poly_data](https://github.com/warproxxx/poly_data))
- `processed/trades.csv` - Processed trade data (required, with market_id)
- `goldsky/orderFilled.csv` - Raw order events (optional, skipped - needs processing first)

### Output Features

The pipeline generates features including:
- Static features: market metadata, categories, timestamps
- Snapshot features: liquidity, volume, prices, spreads at horizon time
- Trade aggregates: transaction counts, volumes, price statistics
- Derived features: mid-price, spread percentage, liquidity ratios
- Text embeddings: Vector representations of questions/titles (optional)
- Target: Binary classification label (high volume vs low volume)

## Module Structure

- `config.py` - Configuration settings
- `data_loader.py` - Data loading and preprocessing
- `target_engineering.py` - Target variable creation
- `feature_engineering.py` - Feature extraction and engineering
- `embeddings.py` - Text embedding generation
- `utils.py` - Utility functions
- `main.py` - Main pipeline orchestration
- `run.py` - CLI entry point

## Examples

### Process with custom threshold
```python
from data_processing.config import Config
from data_processing.main import main

cfg = Config()
cfg.target_volume_threshold = 100000  # Fixed threshold
main(use_dataset_folder=False)
```

### Generate embeddings only
```python
from data_processing.embeddings import generate_text_embeddings
from data_processing.config import Config

cfg = Config()
embeddings_df = generate_text_embeddings(cfg)
```

## Notes

- The pipeline automatically handles large files with chunked processing
- Empty snapshots/trades are handled gracefully in dataset folder mode
- Progress information is displayed throughout processing
- Output files use chunked writing for efficient I/O
