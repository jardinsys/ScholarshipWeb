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
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://mongo:27017/scholarshipdb")
client = MongoClient(MONGO_URI)
db = client[MONGO_URI.rstrip("/").split("/")[-1] or "scholarshipdb"]
raw_collection = db["raw_results"]

def get_main_content(page):
    """Filters out navbars/footers to reduce ML noise."""
    # List of common content containers
    selectors = ["main", "article", "#content", ".entry-content", ".scholarship-details"]
    for selector in selectors:
        element = page.locator(selector).first
        if element.is_visible():
            return element.inner_text()
    # Fallback to a cleaner body extraction
    return page.evaluate("() => document.querySelector('body').innerText")

def extract_links(page, base_url: str) -> list[str]:
    links = page.eval_on_selector_all("a[href]", "elements => elements.map(el => el.href)")
    valid = []
    for link in links:
        try:
            parsed = urlparse(link)
            if parsed.scheme in ("http", "https"):
                valid.append(urljoin(base_url, link))
        except Exception: continue
    return valid

def crawl_page(url: str, depth: int, page):
    url, _ = urldefrag(url)
    if is_visited(url) or url.split("?")[0].endswith((".pdf", ".png", ".jpg", ".zip")):
        return

    print(f"[worker] Crawling ({depth}): {url}")
    try:
        page.goto(url, timeout=60000, wait_until="domcontentloaded")
        mark_visited(url)
    except Exception as e:
        print(f"[worker] Failed: {e}")
        return

    # Using the new noise-reduction helper
    clean_text = get_main_content(page)
    
    raw_doc = {
        "url": url,
        "title": page.title(),
        "text": clean_text,
        "scraped_at": datetime.utcnow().isoformat(),
    }

    raw_id = raw_collection.insert_one(raw_doc).inserted_id
    doc = raw_collection.find_one({"_id": raw_id})
    cleaned = process_raw_document(doc)

    if cleaned: print(f"[worker] ✓ Scholarship saved: {url}")
    else: print(f"[worker] ✗ Not a scholarship: {url}")

    links = extract_links(page, url)
    base_domain = urlparse(url).netloc
    for link in links:
        if is_visited(link): continue
        if is_aggregator_site(link): push_aggregator(link, depth + 1)
        elif urlparse(link).netloc == base_domain: push_crawler(link, depth + 1)
        else: push_crawler(link, 0)

def run_worker():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        while True:
            item = pop_crawler()
            if item is None:
                time.sleep(SLEEP_SECONDS)
                continue
            url, depth = item
            crawl_page(url, depth, page)

if __name__ == "__main__":
    run_worker()