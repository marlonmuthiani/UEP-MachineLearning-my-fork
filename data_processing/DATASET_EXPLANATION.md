# Training and Test Dataset Structure

## Overview

The pipeline creates **two separate datasets** for different purposes:

1. **Training Dataset** (`markets_ml_p75_dataset.csv`) - Historical data for model training
2. **Prediction Dataset** (`markets_ml_p75_collected.csv`) - Current data for making predictions

**Important:** The pipeline does NOT automatically split data into train/test sets. You need to perform chronological splitting yourself based on `created_at` timestamp to avoid data leakage.

---

## Dataset Structure

### Columns in the Output Dataset

Each row represents **one market** with features extracted at the **24-hour horizon** (24h after market creation).

#### 1. **Identifier Columns**
- `market_id` - Unique market identifier
- `event_id`, `event_slug` - Event information
- `market_slug` - Market slug/URL identifier

#### 2. **Static Features** (from market metadata)
- `category`, `subcategory` - Market categorization
- `created_at` - Market creation timestamp
- `end_date` - Market end/resolution date
- `market_lifetime_hours` - Total hours from creation to end
- `snapshot_ts` - Timestamp of the snapshot used (24h after creation)
- `time_to_end_hours_at_24h` - Hours remaining until market end (at 24h snapshot)

#### 3. **Snapshot Features** (market state at 24h horizon)
- `liquidity`, `liquidityAmm`, `liquidityClob` - Liquidity metrics
- `openInterest` - Open interest
- `lastTradePrice` - Last trade price
- `bestBid`, `bestAsk` - Best bid/ask prices
- `spread` - Bid-ask spread
- `volume24hr`, `volume1wk`, `volume1mo` - Volume metrics
- `volume_total` - Total volume (at snapshot time)
- `score` - Market score/ranking

#### 4. **Derived Snapshot Features**
- `mid_price_24h` - Mid-price: (bestBid + bestAsk) / 2
- `spread_pct_24h` - Spread as percentage of mid-price
- `liquidity_per_vol24h` - Liquidity ratio

#### 5. **Trade Aggregation Features** (trades within first 24h)
- `trade_count_0_24h` - Number of unique transactions
- `usd_vol_0_24h` - Total USD volume
- `token_vol_0_24h` - Total token volume
- `price_mean_0_24h` - Mean trade price
- `price_std_0_24h` - Standard deviation of trade prices

#### 6. **Text Embeddings** (optional, if `--embeddings` flag used)
- `question_embedding_dim0` through `question_embedding_dim383` (384 dimensions)
- Or `event_question_embedding_dim0` through `event_question_embedding_dim383`
- Or `market_title_embedding_dim0` through `market_title_embedding_dim383`

#### 7. **Target Variable**
- `final_volume_total` - Final total volume (ground truth)
- `target_high_volume` - Binary target (1 = high volume, 0 = low volume)
  - Threshold: 75th percentile by default (configurable)

---

## Data Processing Pipeline

### Training Dataset Processing (`--use-external-dataset`)

**Input Files:**
- `dataset/markets.csv` - Historical market data
- `dataset/processed/trades.csv` - Historical trade transactions (33GB)
  - **Note:** This is processed trade data. Raw `orderFilled.csv` from Goldsky subgraph is NOT used directly as it lacks `market_id`. 
  - The processing pipeline (from [poly_data](https://github.com/warproxxx/poly_data)) converts raw order events into structured trades with market mappings.

**Processing Steps:**

1. **Load Markets** (49.6MB)
   - Parse market metadata
   - Extract creation/end dates
   - Calculate market lifetime

2. **Create Target Variable**
   - Use final volume from markets.csv
   - Calculate 75th percentile threshold
   - Create binary target: `target_high_volume` (1 if volume ≥ threshold)

3. **Get Snapshot at Horizon**
   - For dataset mode: Creates placeholder snapshots (no actual snapshot data)
   - Sets snapshot timestamp to `created_at + 24 hours`
   - All snapshot features set to 0.0 (no historical snapshot data available)

4. **Aggregate Trades** (incremental processing for 33GB file)
   - Process trades.csv in 1M-row chunks
   - Filter trades to first 24 hours after market creation
   - Aggregate by market_id:
     - Count unique transactions
     - Sum USD and token volumes
     - Calculate price statistics (mean, std)

5. **Build Features**
   - Combine static, snapshot, and trade features
   - Create derived features (mid-price, spread %, liquidity ratios)

6. **Post-processing**
   - Remove outliers (z-score > 8.0)
   - Remove rows with missing targets

**Output:** `dataset/modeling/markets_ml_p75_dataset.csv`

---

### Prediction Dataset Processing (default, no flag)

**Input Files:**
- `data/markets_static.csv` - Current market data
- `data/markets_snapshots.csv` - Current market snapshots
- `dataset/processed/trades.csv` - Current trades (if available)

**Processing Steps:**

1. **Load Markets** (from `data/markets_static.csv`)
   - Parse market metadata
   - Extract creation/end dates

2. **Create Target Variable**
   - Use final volume from markets_static.csv (if available)
   - For active markets: target may be missing (will be filtered out)

3. **Get Snapshot at Horizon**
   - Find snapshot closest to 24h after market creation
   - Uses actual snapshot data from `markets_snapshots.csv`
   - Tolerance: ±6 hours (configurable)

4. **Aggregate Trades**
   - Process trades from `dataset/processed/trades.csv` (if exists)
   - Same aggregation as training dataset

5. **Build Features**
   - Same feature engineering as training

6. **Post-processing**
   - Remove outliers
   - Remove rows with missing targets (active markets without final volume)

**Output:** `dataset/modeling/markets_ml_p75_collected.csv`

---

## Train/Test Split Strategy

**The pipeline does NOT automatically split data.** You must split chronologically to avoid data leakage.

### Recommended Approach:

```python
import pandas as pd
from sklearn.model_selection import train_test_split

# Load the training dataset
df = pd.read_csv('dataset/modeling/markets_ml_p75_dataset_with_embeddings.csv')

# Sort by creation date to ensure chronological order
df = df.sort_values('created_at')

# Split chronologically (70-80% train, 20-30% test)
split_idx = int(len(df) * 0.75)  # 75% train, 25% test

train_df = df.iloc[:split_idx]
test_df = df.iloc[split_idx:]

# Verify no data leakage
print(f"Train date range: {train_df['created_at'].min()} to {train_df['created_at'].max()}")
print(f"Test date range: {test_df['created_at'].min()} to {test_df['created_at'].max()}")
assert train_df['created_at'].max() < test_df['created_at'].min()

# Save splits
train_df.to_csv('dataset/modeling/train.csv', index=False)
test_df.to_csv('dataset/modeling/test.csv', index=False)
```

### Alternative: Time-based Split

```python
# Split by date threshold
split_date = pd.to_datetime('2024-01-01')  # Example threshold

train_df = df[df['created_at'] < split_date]
test_df = df[df['created_at'] >= split_date]
```

---

## Key Differences: Training vs Prediction Datasets

| Aspect | Training Dataset | Prediction Dataset |
|--------|-----------------|-------------------|
| **Source** | `dataset/markets.csv` | `data/markets_static.csv` |
| **Snapshots** | Placeholder (all 0.0) | Real snapshot data |
| **Trades** | Historical (33GB) | Current (if available) |
| **Target** | Always present | May be missing (active markets) |
| **Purpose** | Model training | Making predictions |
| **Size** | ~119k markets | ~7k markets (current) |

---

## Feature Engineering Details

### Time Horizon Concept

All features are extracted at a **fixed time horizon**: 24 hours after market creation.

- **Why?** To simulate making predictions early in a market's lifecycle
- **Snapshot features**: Market state at 24h mark
- **Trade features**: Aggregated trades from first 24h
- **Static features**: Market metadata (unchanging)

### Target Creation

- **Binary Classification**: `target_high_volume` (0 or 1)
- **Threshold**: 75th percentile of `final_volume_total` (default)
- **Interpretation**: 
  - 1 = Market will have high volume (top 25%)
  - 0 = Market will have low volume (bottom 75%)

### Missing Data Handling

- **Snapshot features**: Filled with 0.0 if missing
- **Trade features**: Filled with 0.0 if no trades in first 24h
- **Outliers**: Removed using z-score threshold (default: 8.0)
- **Missing targets**: Rows removed (can't train/predict without target)

---

## Usage Workflow

### 1. Prepare Training Data

```bash
# Generate embeddings for training data
python -m data_processing.embeddings --use-external-dataset

# Process training dataset with embeddings
python -m data_processing.run --use-external-dataset --embeddings
```

### 2. Split into Train/Test

```python
# Use the script above to split chronologically
# Save as train.csv and test.csv
```

### 3. Train Model

```python
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

train = pd.read_csv('dataset/modeling/train.csv')
test = pd.read_csv('dataset/modeling/test.csv')

# Separate features and target
feature_cols = [col for col in train.columns 
                if col not in ['market_id', 'final_volume_total', 'target_high_volume']]
X_train = train[feature_cols]
y_train = train['target_high_volume']
X_test = test[feature_cols]
y_test = test['target_high_volume']

# Train model
model = RandomForestClassifier()
model.fit(X_train, y_train)

# Evaluate
from sklearn.metrics import f1_score, roc_auc_score
y_pred = model.predict(X_test)
print(f"F1-Score: {f1_score(y_test, y_pred)}")
print(f"ROC-AUC: {roc_auc_score(y_test, model.predict_proba(X_test)[:, 1])}")
```

### 4. Make Predictions on Current Data

```bash
# Process current data
python -m data_processing.run --embeddings

# Load and predict
python
>>> import pandas as pd
>>> current = pd.read_csv('dataset/modeling/markets_ml_p75_collected_with_embeddings.csv')
>>> predictions = model.predict_proba(current[feature_cols])
>>> current['predicted_high_volume_prob'] = predictions[:, 1]
```

---

## Summary

- **Training dataset**: Historical data with placeholder snapshots, used for model training
- **Prediction dataset**: Current data with real snapshots, used for making predictions
- **No automatic split**: You must split chronologically yourself
- **Features**: Static metadata + snapshot state at 24h + trade aggregates from first 24h + optional embeddings
- **Target**: Binary classification (high volume vs low volume) based on 75th percentile threshold
