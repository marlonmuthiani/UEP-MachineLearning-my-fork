import time
from run_events_snapshot import collect_events_snapshot
from datetime import datetime

INTERVAL_MINUTES = 20

if __name__ == "__main__":
    while True:
        print(f"=== SNAPSHOT: {datetime.now()} ===")
        collect_events_snapshot(limit=100, max_pages=20)
        print(f"Oczekiwanie {INTERVAL_MINUTES} minut...")
        time.sleep(INTERVAL_MINUTES * 60)