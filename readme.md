# Polymarket ML Analysis Project

A machine learning pipeline for analyzing Polymarket prediction markets data, focusing on predicting user engagement and market volume using gradient boosting models.

---

## Project Overview

This project builds a complete ML pipeline for Polymarket analysis:
- **Data Collection**: Automated scripts to collect market data via Polymarket Gamma API
- **Data Processing**: Feature engineering with text embeddings and temporal features
- **ML Modeling**: Classification and regression models (XGBoost, LightGBM, CatBoost) for volume prediction
- **Target**: Predict whether a market will have high trading volume (>10k USD threshold)

---

## Repository Structure

```
UEP-MachineLearning/
├── get_data/                    # Data Collection Scripts
│   ├── polymarket_events_collector.py  # Gamma API client
│   ├── data_writer.py                  # CSV data writer with schema
│   ├── run_events_snapshot.py          # Main collection script
│   ├── migrate_csv_schema.py           # Schema migration utility
│   └── scheduler.py                    # Automated 20-min collection
│
├── notebooks/                   # Jupyter Notebooks
│   ├── data_prep.ipynb         # Data loading and preprocessing
│   ├── data_fe.ipynb           # Feature engineering + embeddings
│   ├── model_training.ipynb    # Model training with hyperparameter search
│   └── model_prediction.ipynb  # Model evaluation and predictions
│
├── data_collected/             # Raw collected data (gitignored)
│   ├── markets_static.csv      # Market metadata (~13MB)
│   └── markets_snapshots.csv   # Time-series snapshots (~84MB)
│
├── data_enriched/              # Processed/enriched data
│   ├── p_markets.csv           # Processed markets
│   ├── p_orderFilled.csv       # Order fill data
│   └── p_trades.csv            # Trade data
│
├── data_model/                 # ML-ready datasets (gitignored)
│   ├── db_collected.csv        # Main collected dataset (~2.7GB)
│   └── db_additional.csv       # Additional features
│
├── models/                     # Saved trained models
├── notebooks_old/              # Deprecated notebooks
│   ├── embedding.ipynb
│   └── preparation_for_embedding.ipynb
│
├── explaination_poly.md        # Detailed pipeline documentation
├── col names and types.txt     # Column schema reference
└── readme.md                   # This file
```

---

## Data Collection Pipeline

### Gamma API Client (`polymarket_events_collector.py`)

Interfaces with Polymarket's Gamma API:
```python
class GammaAPIClient:
    """Fetches events and markets from Polymarket."""
    def get_events(limit, offset, active, closed, archived, order, ascending)
```

### Data Schema

**Static Fields** (`markets_static.csv`):
| Field | Description |
|-------|-------------|
| `market_id` | Unique market identifier |
| `event_id`, `event_slug`, `event_title` | Event metadata |
| `question` | Market question text |
| `category`, `subcategory` | Market categorization |
| `created_at`, `end_date` | Lifecycle timestamps |
| `resolution_source` | Resolution authority |

**Snapshot Fields** (`markets_snapshots.csv`):
| Field | Description |
|-------|-------------|
| `snapshot_ts` | Timestamp of data collection |
| `active`, `closed`, `featured`, `new` | Market status flags |
| `volume24hr`, `volume1wk`, `volume1mo` | Volume metrics |
| `liquidity`, `liquidityClob` | Liquidity metrics |
| `bestBid`, `bestAsk`, `spread` | Price data |
| `lastTradePrice` | Last trade price |

### Running Data Collection

```bash
# Single snapshot
cd get_data
python run_events_snapshot.py

# Continuous collection (every 20 minutes)
python scheduler.py
```

---

## ML Pipeline

### 1. Data Preparation (`data_prep.ipynb`)

- Loads raw CSV data from `data_collected/`
- Handles mixed types and schema inconsistencies
- Merges static and snapshot data

### 2. Feature Engineering (`data_fe.ipynb`)

Key transformations:
- **Text Embeddings**: Uses sentence-transformers for `question` field (384-dim)
- **Temporal Features**: `start_time`, `end_time`, market duration
- **Missing Value Handling**: Strategy per data type (0.0 for numeric, empty for strings)
- **Boolean Encoding**: Convert to `uint8`

```python
def data_fe(df, model):
    # Filter active markets
    df = df[df['volume_total'] > 0]
    
    # Generate text embeddings
    df = generate_embedding(df, 'question', model)
    
    # Explode embeddings to individual columns
    df = explode_embeddings(df, ['question_emb'])
    
    return df
```

### 3. Model Training (`model_training.ipynb`)

**Models Compared**:
| Model | Type | Target Transform |
|-------|------|------------------|
| XGBoost | Regressor | None |
| LightGBM | Regressor | None |
| CatBoost | Regressor | None |
| XGBoost Log | Regressor | log1p/expm1 |
| LightGBM Log | Regressor | log1p/expm1 |
| Random Forest Log | Regressor | log1p/expm1 |

**Hyperparameter Search**: RandomizedSearchCV with cross-validation

**Classification Target**: 
```python
y = (df["volume_total"] > 10_000).astype(int)  # High volume = >$10k
```

**Key Hyperparameters Tuned**:
- `n_estimators`: 200-1200
- `max_depth`: 3-20
- `learning_rate`: 0.01-0.1
- `num_leaves`: 16-256 (LightGBM)
- `subsample`, `colsample_bytree`: 0.6-1.0

### 4. Model Evaluation (`model_prediction.ipynb`)

**Classification Metrics**:
- Confusion Matrix (TN, FP, FN, TP)
- Precision, Recall, F1-Score
- ROC-AUC, Precision-Recall Curve
- False Negative Rate

**Regression Metrics**:
- RMSE (Root Mean Squared Error)
- MAE (Mean Absolute Error)
- R² Score

---

## Data Flow Diagram

```
Polymarket API
      │
      ▼
┌─────────────────┐
│ get_events()    │──► markets_static.csv
│ (Gamma API)     │──► markets_snapshots.csv
└─────────────────┘
      │
      ▼
┌─────────────────┐
│ data_prep.ipynb │──► Merged DataFrame
└─────────────────┘
      │
      ▼
┌─────────────────┐
│ data_fe.ipynb   │──► db_collected.csv (with embeddings)
│ (Embeddings)    │
└─────────────────┘
      │
      ▼
┌─────────────────┐
│ model_training  │──► Trained Models (.joblib)
│ (XGB/LGBM/CB)   │
└─────────────────┘
      │
      ▼
┌─────────────────┐
│ model_predict   │──► Predictions & Metrics
└─────────────────┘
```

---

## Quick Start

### Recovery

To restore the full development environment:
```bash
# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install all dependencies
pip install -r requirements.txt
```

### Prerequisites
```bash
pip install pandas numpy scikit-learn xgboost lightgbm catboost sentence-transformers requests
```

### 1. Collect Data
```bash
cd get_data
python run_events_snapshot.py
```

### 2. Process Data
Open and run notebooks in order:
1. `notebooks/data_prep.ipynb`
2. `notebooks/data_fe.ipynb`

### 3. Train Models
```bash
# Run model_training.ipynb
```

### 4. Make Predictions
```bash
# Run model_prediction.ipynb
```

---

## ML Analyses

| Analysis | Goal | Model Type |
|----------|------|------------|
| **Classification** | Predict if market exceeds 10k volume | XGBoost/LightGBM Classifier |
| **Regression** | Predict exact `volume_total` value | XGBoost/LightGBM/CatBoost Regressor |
| **Clustering** | Segment markets by behavior | (Planned) |

---

## Key Features Used

**Numeric Features**:
- `volume24hr`, `volume1wk`, `volume1mo`, `volume_total`
- `liquidity`, `liquidityClob`
- `bestBid`, `bestAsk`, `spread`
- `lastTradePrice`, `oneDayPriceChange`

**Text Features**:
- `question` → 384-dimensional embeddings

**Temporal Features**:
- `start_time`, `end_time`
- Market duration

**Boolean Flags**:
- `active`, `closed`, `featured`, `new`

---

## File Size Reference

| File | Size | Description |
|------|------|-------------|
| `markets_snapshots.csv` | ~84 MB | Time-series data |
| `markets_static.csv` | ~13 MB | Market metadata |
| `db_collected.csv` | ~2.7 GB | ML-ready dataset with embeddings |

---

## Configuration

### Scheduler Settings
```python
INTERVAL_MINUTES = 20  # Collection frequency
MAX_PAGES = 20         # Pages per collection (100 events/page)
```

### API Settings
```python
GAMMA_BASE_URL = "https://gamma-api.polymarket.com"
TIMEOUT = 15  # seconds
```

---

## References

- **Polymarket Gamma API**: Primary data source for events and markets
- **Sentence Transformers**: For text embedding generation
- **XGBoost/LightGBM/CatBoost**: Gradient boosting implementations

---

## Notes

- Data collection should be run continuously for time-series analysis
- The `data_model/` directory is gitignored due to large file sizes
- Chronological train/test split recommended to avoid data leakage
- See `explaination_poly.md` for detailed dataset structure documentation