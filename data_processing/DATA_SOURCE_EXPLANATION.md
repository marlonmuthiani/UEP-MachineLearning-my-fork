# Data Source Structure - Understanding poly_data Repository

Based on the [poly_data repository](https://github.com/warproxxx/poly_data), this document explains the data pipeline and how our processing integrates with it.

## Data Pipeline Overview

The poly_data repository provides a 3-stage pipeline:

1. **Update Markets** → `markets.csv`
2. **Update Goldsky** → `goldsky/orderFilled.csv` (RAW)
3. **Process Live Trades** → `processed/trades.csv` (PROCESSED)

## File Structure

### 1. `markets.csv` (Source: Polymarket API)

**Purpose:** Market metadata from Polymarket API

**Columns:**
- `id` - Market ID
- `createdAt`, `closedTime` - Timestamps
- `question` - Market question text
- `answer1`, `answer2` - Market outcomes
- `market_slug` - URL slug
- `token1`, `token2` - Outcome token IDs
- `condition_id` - Market condition ID
- `volume` - Trading volume
- `neg_risk` - Negative risk indicator
- `ticker` - Market ticker

**Usage in our pipeline:** Loaded directly as historical market data

---

### 2. `goldsky/orderFilled.csv` (Source: Goldsky Subgraph)

**Purpose:** Raw order-filled events from blockchain

**Columns:**
- `timestamp` - Unix timestamp
- `maker` - Maker wallet address
- `makerAssetId` - Asset ID (0 = USDC, non-zero = outcome token)
- `makerAmountFilled` - Amount filled (raw units, divide by 10^6)
- `taker` - Taker wallet address
- `takerAssetId` - Asset ID
- `takerAmountFilled` - Amount filled
- `transactionHash` - Blockchain transaction hash

**Important:** This file does NOT have `market_id` - it's raw blockchain data that needs processing.

**Processing Required:** Must be converted to `processed/trades.csv` using the `process_live.py` script from poly_data.

**Why we skip it:** Our pipeline requires `market_id` for aggregation, so we only use the processed version.

---

### 3. `processed/trades.csv` (Source: Processed from orderFilled.csv)

**Purpose:** Structured trade data with market mappings

**Columns:**
- `timestamp` - Trade timestamp (datetime)
- `market_id` - **Market ID (mapped from asset IDs)**
- `maker`, `taker` - Wallet addresses
- `nonusdc_side` - Which side is non-USDC (token1 or token2)
- `maker_direction` - BUY or SELL
- `taker_direction` - BUY or SELL
- `price` - Price in USDC per outcome token
- `usd_amount` - USD volume (normalized)
- `token_amount` - Token volume (normalized)
- `transactionHash` - Transaction hash

**Processing Logic (from poly_data):**
1. Maps `makerAssetId`/`takerAssetId` to markets using token lookup
2. Identifies non-USDC asset (outcome token)
3. Determines BUY/SELL directions:
   - Taker BUY if paying USDC, SELL if receiving USDC
   - Maker direction is opposite
4. Calculates price as USDC per outcome token
5. Normalizes amounts (divides by 10^6)

**Usage in our pipeline:** This is what we use for trade aggregation features.

---

## Our Pipeline Integration

### What We Use

✅ **`dataset/markets.csv`** - Market metadata
✅ **`dataset/processed/trades.csv`** - Processed trades (with market_id)

### What We Skip

❌ **`dataset/goldsky/orderFilled.csv`** - Raw data without market_id

### Why This Design?

1. **Separation of Concerns:** 
   - poly_data handles raw data collection and processing
   - Our pipeline focuses on feature engineering and ML preparation

2. **Data Integrity:**
   - Processed trades.csv ensures correct market mappings
   - Avoids duplicate processing logic

3. **Performance:**
   - Processed trades.csv is already optimized
   - We can aggregate directly without re-processing

---

## Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    poly_data Repository                      │
│                                                             │
│  1. Polymarket API → markets.csv                           │
│  2. Goldsky Subgraph → goldsky/orderFilled.csv (RAW)      │
│  3. process_live.py → processed/trades.csv (PROCESSED)     │
└─────────────────────────────────────────────────────────────┘
                          │
                          │ (Copy to our dataset/)
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              Our ML Pipeline                                │
│                                                             │
│  markets.csv → Market features                              │
│  processed/trades.csv → Trade aggregation features         │
│  (Skip orderFilled.csv - already processed)                 │
└─────────────────────────────────────────────────────────────┘
```

---

## Key Insights from poly_data

### Trade Direction Logic

- **Taker Direction:** 
  - BUY if paying USDC (takerAssetId = 0)
  - SELL if receiving USDC (makerAssetId = 0)
  
- **Maker Direction:** Opposite of taker

- **Price:** Always USDC per outcome token

### Asset Mapping

- Asset ID `0` = USDC
- Non-zero Asset IDs = Outcome tokens (token1 or token2 from markets)
- Each trade involves USDC + one outcome token

### Amount Normalization

All amounts are divided by 10^6 to convert from raw blockchain units to standard decimals.

### Missing Market Discovery

The poly_data `process_live.py` automatically discovers markets that weren't in the initial `markets.csv` (e.g., markets created after last update) and fetches them via Polymarket API, saving to `missing_markets.csv`.

---

## Recommendations

### If You Need to Process orderFilled.csv

If you have raw `orderFilled.csv` but no `processed/trades.csv`, you should:

1. **Use poly_data processing:**
   ```bash
   git clone https://github.com/warproxxx/poly_data
   cd poly_data
   uv sync
   uv run python -c "from update_utils.process_live import process_live; process_live()"
   ```

2. **Or implement similar logic:**
   - Map asset IDs to markets using token lookup
   - Calculate prices and directions
   - Normalize amounts
   - Save as `processed/trades.csv`

### Current Setup (Recommended)

✅ Use pre-processed `trades.csv` - faster and more reliable
✅ Skip `orderFilled.csv` - already processed
✅ Focus on feature engineering and ML

---

## References

- [poly_data Repository](https://github.com/warproxxx/poly_data)
- [Polymarket API Documentation](https://docs.polymarket.com/)
- [Goldsky Subgraph](https://goldsky.com/)
