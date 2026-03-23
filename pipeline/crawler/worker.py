import os
import time
from datetime import datetime
from urllib.parse import urldefrag, urlparse, urljoin
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

SLEEP_SECONDS = 10

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/scholarshipdb")
_db_name  = MONGO_URI.rstrip("/").split("/")[-1] or "scholarshipdb"
client    = MongoClient(MONGO_URI)
db        = client[_db_name]
raw_collection = db["raw_results"]


def extract_links(page, base_url: str) -> list[str]:
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


def get_provider(page) -> str:
    """
    Extract a human-readable org/site name from page metadata.
    Tries og:site_name first, falls back to empty string
    (ml_pipeline._extract_provider will derive it from the domain).
    """
    try:
        og_site = page.get_attribute('meta[property="og:site_name"]', 'content')
        if og_site and og_site.strip():
            return og_site.strip()
    except Exception:
        pass
    return ""


def crawl_page(url: str, depth: int, page):
    url, _ = urldefrag(url)

    if url.split("?")[0].endswith((".pdf", ".zip", ".docx", ".png", ".jpg", ".jpeg", ".gif", ".svg")):
        print(f"[worker] Skipping non-HTML file: {url}")
        return

    if is_visited(url):
        return

    print(f"[worker] Crawling ({depth}): {url}")

    try:
        page.goto(url, timeout=60000)
        mark_visited(url)
    except Exception as e:
        print(f"[worker] Failed to load {url}: {e}")
        return

    raw_doc = {
        "url":        url,
        "title":      page.title(),
        "text":       page.inner_text("body"),
        "provider":   get_provider(page),
        "scraped_at": datetime.utcnow().isoformat(),
    }

    raw_id  = raw_collection.insert_one(raw_doc).inserted_id
    doc     = raw_collection.find_one({"_id": raw_id})
    cleaned = process_raw_document(doc)

    if cleaned:
        print(f"[worker] ✓ Scholarship saved: {url}")
    else:
        print(f"[worker] ✗ Not a scholarship: {url}")

    links       = extract_links(page, url)
    base_domain = urlparse(url).netloc

    for link in links:
        if is_visited(link):
            continue
        link_domain = urlparse(link).netloc
        if is_aggregator_site(link):
            push_aggregator(link, depth + 1)
        elif link_domain == base_domain:
            push_crawler(link, depth + 1)
        else:
            push_crawler(link, 0)


def run_worker():
    print(f"[worker] Starting crawler worker at {datetime.utcnow().isoformat()}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page    = browser.new_page()

        while True:
            item = pop_crawler()
            if item is None:
                stats = queue_stats()
                print(f"[worker] Queue empty. Waiting {SLEEP_SECONDS}s… Stats: {stats}")
                time.sleep(SLEEP_SECONDS)
                continue
            url, depth = item
            crawl_page(url, depth, page)


if __name__ == "__main__":
    run_worker()