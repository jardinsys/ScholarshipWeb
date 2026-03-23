"""
Test script to manually pushes 2 URLs into Redis and runs the worker
to verify the full pipeline works end to end. (preliminary to aggregator + worker)

Not used in Docker anymore

Expected results:
  https://www.servicescape.com/scholarship → detected as scholarship, saved to MongoDB
  https://www.example.com                  → skipped, not a scholarship
"""

from crawler.redis_queue import push_crawler, queue_stats
from crawler.worker import run_worker

def seed_test_urls():
    push_crawler("https://www.servicescape.com/scholarship", depth=0)
    push_crawler("https://www.example.com", depth=0)
    print(f"[test] Seeded 2 URLs. Stats: {queue_stats()}")

if __name__ == "__main__":
    seed_test_urls()
    run_worker()