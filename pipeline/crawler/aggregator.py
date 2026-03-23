import os
import json
import time
import schedule
from datetime import datetime
from urllib.parse import urlparse, urljoin
from playwright.sync_api import sync_playwright
from crawler.redis_queue import (
    add_aggregator_site,
    get_aggregator_sites,
    is_aggregator_site,
    push_aggregator,
    pop_aggregator,
    push_crawler,
    mark_visited,
    is_visited,
    queue_stats,
)

SEEDS_PATH        = "/app/seeds/aggregators.json"
SAME_DOMAIN_DEPTH = 4
EXTERNAL_DEPTH    = 0


# Seed Redis
def load_seeds():
    """Load aggregator sites from JSON into Redis on startup."""
    with open(SEEDS_PATH, "r") as f:
        sites = json.load(f)
    for site in sites:
        add_aggregator_site(site)
    print(f"[aggregator] Loaded {len(sites)} seed sites into Redis.")


# Link extractor 
def extract_links(page, base_url: str) -> list[str]:
    """Extract all valid http/https links from the current page."""
    links = page.eval_on_selector_all(
        "a[href]",
        "elements => elements.map(el => el.href)"
    )
    valid = []
    for link in links:
        try:
            parsed = urlparse(link)
            if parsed.scheme in ("http", "https"):
                full = urljoin(base_url, link)
                valid.append(full)
        except Exception:
            continue
    return valid


# Single page crawl 
def crawl_page(url: str, depth: int, page):
    """
    Scrape a single aggregator page and sort its links into the correct queues.
    - Same aggregator domain → push to aggregator queue (recursive)
    - External link → push to crawler queue
    """
    if is_visited(url):
        return

    print(f"[aggregator] Crawling ({depth}): {url}")

    try:
        page.goto(url, timeout=60000)
        mark_visited(url)
    except Exception as e:
        print(f"[aggregator] Failed to load {url}: {e}")
        return

    links       = extract_links(page, url)
    base_domain = urlparse(url).netloc

    same_domain = 0
    external    = 0

    for link in links:
        link_domain = urlparse(link).netloc

        if is_visited(link):
            continue

        if link_domain == base_domain:
            push_aggregator(link, depth + 1)
            same_domain += 1
        else:
            push_crawler(link, EXTERNAL_DEPTH)
            external += 1

    print(f"[aggregator] Found {same_domain} same-domain, {external} external links on {url}")


# Main aggregator run 
def run_aggregator():
    print(f"\n[aggregator] Starting run at {datetime.utcnow().isoformat()}")

    sites = get_aggregator_sites()
    print(f"[aggregator] {len(sites)} aggregator sites to seed from.")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page    = browser.new_page()

        for site in sites:
            push_aggregator(site, depth=0)

        while True:
            item = pop_aggregator()
            if item is None:
                break
            url, depth = item
            crawl_page(url, depth, page)
            time.sleep(1) # Polite throttle

        browser.close()

    print(f"[aggregator] Run complete. Stats: {queue_stats()}")


# Scheduler 
if __name__ == "__main__":
    load_seeds()
    run_aggregator()

    schedule.every(24).hours.do(run_aggregator)
    print("[aggregator] Scheduled to run every 24 hours.")

    while True:
        schedule.run_pending()
        time.sleep(60)