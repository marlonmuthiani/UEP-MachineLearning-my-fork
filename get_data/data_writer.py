import os
import csv
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple

DATA_DIR = "data"
STATIC_PATH = os.path.join(DATA_DIR, "markets_static.csv")
SNAPSHOT_PATH = os.path.join(DATA_DIR, "markets_snapshots.csv")


STATIC_FIELDS = [
    "market_id",
    "event_id",
    "event_slug",
    "event_title",
    "market_slug",
    "question",
    "category",
    "subcategory",
    "created_at",
    "end_date",
    "resolution_source",
    "commentCount",
]

SNAPSHOT_FIELDS = [
    "snapshot_ts",
    "market_id",
    "active",
    "closed",
    "featured",
    "new",
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
]


def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def init_csv_if_needed(path: str, header: List[str]) -> None:
    if not os.path.exists(path):
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=header)
            writer.writeheader()


def load_existing_ids(path: str, key_field: str) -> set:
    if not os.path.exists(path):
        return set()
    ids = set()
    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ids.add(row[key_field])
    return ids


def append_rows(path: str, header: List[str], rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        for r in rows:
            writer.writerow(r)


def process_events_into_rows(events: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Z surowych eventów z API zbuduj listę:
    - static_rows: markets_static
    - snapshot_rows: markets_snapshots
    """
    snapshot_ts = datetime.now(timezone.utc).isoformat()
    static_rows: List[Dict[str, Any]] = []
    snapshot_rows: List[Dict[str, Any]] = []

    for ev in events:
        event_id = ev.get("id")
        event_slug = ev.get("slug")
        event_title = ev.get("title")
        category = ev.get("category") or ""
        subcategory = ev.get("subcategory") or ""

        markets = ev.get("markets") or []
        for m in markets:
            market_id = m.get("id")
            if not market_id:
                continue

            static_rows.append(
                {
                    "market_id": str(market_id),
                    "event_id": str(event_id) if event_id else "",
                    "event_slug": event_slug or "",
                    "event_title": event_title or "",
                    "market_slug": m.get("slug") or "",
                    "question": m.get("question") or m.get("title") or "",
                    "category": category or (m.get("category") or ""),
                    "subcategory": subcategory or (m.get("subcategory") or ""),
                    "created_at": m.get("createdAt") or "",
                    "end_date": m.get("endDate") or m.get("umaEndDate") or "",
                    "resolution_source": m.get("resolutionSource") or "",
                }
            )

            # Pola pomocnicze z fallbackami
            volume24hr = (
                m.get("volume24hr")
                or m.get("volume24hrNum")
                or ""
            )
            volume1wk = m.get("volume1wk") or ""
            volume1mo = m.get("volume1mo") or ""
            volume1yr = m.get("volume1yr") or ""
            volume_total = m.get("volume") or m.get("volumeNum") or ""

            liquidity = m.get("liquidity") or m.get("liquidityNum") or ""
            liquidity_amm = m.get("liquidityAmm") or ""
            liquidity_clob = m.get("liquidityClob") or ""

            last_trade_price = m.get("lastTradePrice") or ""
            best_bid = m.get("bestBid") or ""
            best_ask = m.get("bestAsk") or ""
            spread = m.get("spread") or ""

            one_day_change = m.get("oneDayPriceChange") or ""
            one_week_change = m.get("oneWeekPriceChange") or ""

            comment_count = m.get("commentCount") or ""
            competitive = m.get("competitive") or ""
            score = m.get("score") or ""

            open_interest = m.get("openInterest") or ""

            snapshot_rows.append(
                {
                    "snapshot_ts": snapshot_ts,
                    "market_id": str(market_id),
                    "active": str(m.get("active", "")),
                    "closed": str(m.get("closed", "")),
                    "featured": str(m.get("featured", "")),
                    "new": str(m.get("new", "")),
                    "volume24hr": volume24hr,
                    "volume1wk": volume1wk,
                    "volume1mo": volume1mo,
                    "volume1yr": volume1yr,
                    "volume_total": volume_total,
                    "liquidity": liquidity,
                    "liquidityAmm": liquidity_amm,
                    "liquidityClob": liquidity_clob,
                    "openInterest": open_interest,
                    "lastTradePrice": last_trade_price,
                    "bestBid": best_bid,
                    "bestAsk": best_ask,
                    "spread": spread,
                    "oneDayPriceChange": one_day_change,
                    "oneWeekPriceChange": one_week_change,
                    "commentCount": comment_count,
                    "competitive": competitive,
                    "score": score,
                }
            )

    return static_rows, snapshot_rows