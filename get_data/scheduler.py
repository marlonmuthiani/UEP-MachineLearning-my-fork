import time
from run_events_snapshot import collect_events_snapshot

INTERVAL_MINUTES = 10

if __name__ == "__main__":
    while True:
        print("=== RUN SNAPSHOT ===")
        collect_events_snapshot(limit=100, max_pages=20)
        print(f"Oczekiwanie {INTERVAL_MINUTES} minut...")
        time.sleep(INTERVAL_MINUTES * 60)