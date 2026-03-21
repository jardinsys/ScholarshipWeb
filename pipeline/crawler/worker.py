import time
from datetime import datetime
from urllib.parse import urlparse, urljoin
from playwright.sync_api import sync_playwright
from ml.ml_pipeline import process_raw_document
from crawler.redis_queue import (
    is_aggregator_site,
    push_aggregator,
    push_crawler,
    pop_crawler,
    mark_visited,
    is_visited,
    queue_stats
)
from pymongo import MongoClient

SLEEP_SECONDS = 10  # Wait time when queue is empty before checking again

# MongoDB setup
client = MongoClient("mongodb://mongo:27017")
db = client["scholarship_crawler"]
raw_collection = db["raw_results"]


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
    Scrape a page, run ML pipeline, and sort its links into queues.
    - If ML detects a scholarship → save to MongoDB
    - If link is on a known aggregator → push to aggregator queue
    - Otherwise → push to crawler queue
    """
    if is_visited(url):
        return

    print(f"[worker] Crawling ({depth}): {url}")

    try:
        page.goto(url, timeout=60000)
        mark_visited(url)
    except Exception as e:
        print(f"[worker] Failed to load {url}: {e}")
        return

    # Build raw doc and run ML pipeline
    raw_doc = {
        "url": url,
        "title": page.title(),
        "text": page.inner_text("body"),
        "scraped_at": datetime.utcnow().isoformat()
    }

    raw_id = raw_collection.insert_one(raw_doc).inserted_id
    doc = raw_collection.find_one({"_id": raw_id})
    cleaned = process_raw_document(doc)

    if cleaned:
        print(f"[worker] ✓ Scholarship saved: {url}")
    else:
        print(f"[worker] ✗ Not a scholarship: {url}")

    # Extract and sort links
    links = extract_links(page, url)
    base_domain = urlparse(url).netloc

    for link in links:
        if is_visited(link):
            continue

        link_domain = urlparse(link).netloc

        if is_aggregator_site(link):
            push_aggregator(link, depth + 1)
        elif link_domain == base_domain:
            # Same domain as current page — stay in crawler queue
            push_crawler(link, depth + 1)
        else:
            # External domain — crawler queue at fresh depth
            push_crawler(link, 0)


# Main worker loop 
def run_worker():
    print(f"[worker] Starting crawler worker at {datetime.utcnow().isoformat()}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        while True:
            item = pop_crawler()

            if item is None:
                stats = queue_stats()
                print(f"[worker] Queue empty. Waiting {SLEEP_SECONDS}s... Stats: {stats}")
                time.sleep(SLEEP_SECONDS)
                continue

            url, depth = item
            crawl_page(url, depth, page)


if __name__ == "__main__":
    run_worker()