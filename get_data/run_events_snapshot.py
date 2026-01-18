from typing import List, Dict, Any

from polymarket_events_collector import GammaAPIClient
from data_writer import (
    ensure_data_dir,
    init_csv_if_needed,
    load_existing_ids,
    append_rows,
    process_events_into_rows,
    STATIC_PATH,
    SNAPSHOT_PATH,
    STATIC_FIELDS,
    SNAPSHOT_FIELDS,
)


def collect_events_snapshot(limit: int = 100, max_pages: int = 10) -> None:
    """
    Pobiera wszystkie aktywne eventy (z rynkami) i zapisuje:
    - nowe rynki do markets_static.csv
    - snapshoty do markets_snapshots.csv
    """
    ensure_data_dir()
    init_csv_if_needed(STATIC_PATH, STATIC_FIELDS)
    init_csv_if_needed(SNAPSHOT_PATH, SNAPSHOT_FIELDS)

    api = GammaAPIClient()

    existing_market_ids = load_existing_ids(STATIC_PATH, "market_id")

    all_static_rows: List[Dict[str, Any]] = []
    all_snapshot_rows: List[Dict[str, Any]] = []

    offset = 0
    pages = 0

    while True:
        events = api.get_events(
            limit=limit,
            offset=offset,
            active=True,
            closed=False,
            archived=False,
            order="id",
            ascending=False,
        )  # aktywne eventy, najnowsze najpierw[web:12]

        if not events:
            break

        static_rows, snapshot_rows = process_events_into_rows(events)

        # filtruj static_rows po nowych market_id
        new_static_rows = [r for r in static_rows if r["market_id"] not in existing_market_ids]
        new_ids = {r["market_id"] for r in new_static_rows}
        existing_market_ids.update(new_ids)

        all_static_rows.extend(new_static_rows)
        all_snapshot_rows.extend(snapshot_rows)

        offset += limit
        pages += 1
        if pages >= max_pages or len(events) < limit:
            break

    append_rows(STATIC_PATH, STATIC_FIELDS, all_static_rows)
    append_rows(SNAPSHOT_PATH, SNAPSHOT_FIELDS, all_snapshot_rows)

    print(f"Zapisano {len(all_static_rows)} nowych rynków do markets_static.csv")
    print(f"Zapisano {len(all_snapshot_rows)} snapshotów do markets_snapshots.csv")


if __name__ == "__main__":
    collect_events_snapshot(limit=100, max_pages=20)
