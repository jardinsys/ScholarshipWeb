"""
search_crawler.py — DuckDuckGo-based active search crawler

Searches DDG for scholarship-related queries and feeds discovered URLs
into the existing worker queue for the ML pipeline to process.

Query sources:
  1. Static seed queries  — broad terms always worth searching
  2. Dynamic queries      — built from tag names + values already in MongoDB

Runs once on startup, then every 12 hours.
"""

import os
import time
import random
import schedule
from datetime import datetime
from urllib.parse import urlparse, quote_plus
from playwright.sync_api import sync_playwright
from pymongo import MongoClient

from crawler.redis_queue import (
    push_crawler,
    push_aggregator,
    is_visited,
    is_aggregator_site,
    queue_stats,
)

# ─── MongoDB ──────────────────────────────────────────────────────────────────

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/scholarshipdb")
_db_name  = MONGO_URI.rstrip("/").split("/")[-1] or "scholarshipdb"
client    = MongoClient(MONGO_URI)
db        = client[_db_name]
tag_collection         = db["tags"]
scholarship_collection = db["scholarships"]

# ─── Constants ────────────────────────────────────────────────────────────────

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

SKIP_DOMAINS = {
    "bing.com", "google.com", "facebook.com", "twitter.com", "x.com",
    "instagram.com", "youtube.com", "linkedin.com", "reddit.com",
    "wikipedia.org", "amazon.com", "ebay.com", "pinterest.com",
    "tiktok.com", "snapchat.com", "microsoft.com", "apple.com",
    "duckduckgo.com",
}

DELAY_MIN = 1.5
DELAY_MAX = 3.5

# ─── Static seed queries ──────────────────────────────────────────────────────

STATIC_QUERIES = [
    "college scholarship application",
    "undergraduate scholarship",
    "graduate scholarship",
    "no essay scholarship",
    "merit scholarship",
    "need based scholarship",
    "stem scholarship",
    "engineering scholarship",
    "nursing scholarship",
    "business scholarship",
    "art scholarship",
    "music scholarship",
    "first generation college student scholarship",
    "minority scholarship",
    "women in stem scholarship",
    "hispanic scholarship fund",
    "black student scholarship",
    "asian american scholarship",
    "native american scholarship",
    "disability scholarship",
    "community college scholarship",
    "transfer student scholarship",
    "renewable scholarship no essay",
    "full ride scholarship undergraduate",
    "local scholarship high school senior",
    "scholarship for single parents",
    "military family scholarship",
    "scholarship for veterans",
    "coding scholarship",
    "data science scholarship",
]

# ─── Dynamic query builder ────────────────────────────────────────────────────

def build_dynamic_queries() -> list[str]:
    queries = []
    seen    = set()

    def add(q: str):
        q = q.strip().lower()
        if q and q not in seen and len(q) > 5:
            seen.add(q)
            queries.append(q)

    try:
        for tag in tag_collection.find({}):
            name = tag.get("name", "").strip()
            if name:
                add(f"{name} scholarship")

        pipeline = [
            {"$unwind": "$tags"},
            {"$group": {"_id": "$tags.tag_value"}},
            {"$limit": 150},
        ]
        for doc in scholarship_collection.aggregate(pipeline):
            val = str(doc.get("_id", "")).strip()
            if val and val.lower() not in ("any", "unspecified") and len(val) > 2:
                add(f"{val} scholarship")

    except Exception as e:
        print(f"[search_crawler] Warning: could not build dynamic queries: {e}")

    print(f"[search_crawler] Built {len(queries)} dynamic queries from MongoDB")
    return queries

# ─── Browser setup ────────────────────────────────────────────────────────────

def make_browser_context(playwright):
    """
    Launch Chromium with anti-detection settings.
    """
    browser = playwright.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--disable-gpu",
        ]
    )
    context = browser.new_context(
        user_agent=USER_AGENT,
        viewport={"width": 1280, "height": 800},
        locale="en-US",
        timezone_id="America/New_York",
        java_script_enabled=True,
        accept_downloads=False,
        extra_http_headers={
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
    )
    context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins',   { get: () => [1, 2, 3] });
        Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        window.chrome = { runtime: {} };
    """)
    return browser, context

# ─── DuckDuckGo search ────────────────────────────────────────────────────────

def search_duckduckgo(query: str, page) -> int:
    """
    Use DDG's plain HTML endpoint — no JS, no bot detection, clean result links.
    Returns the number of new URLs queued.
    """
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    print(f"[search_crawler] DDG: \"{query}\"")

    try:
        page.goto(url, timeout=30000, wait_until="domcontentloaded")
        time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
    except Exception as e:
        print(f"[search_crawler] Failed to load DDG results: {e}")
        return 0

    # Debug: confirm we got a real results page
    try:
        print(f"[search_crawler] Page title: '{page.title()}'")
    except Exception:
        pass

    # DDG html endpoint uses .result__a for organic result links
    links = []
    try:
        for a in page.query_selector_all(".result__a"):
            href = a.get_attribute("href")
            if href and href.startswith("http"):
                links.append(href)
    except Exception as e:
        print(f"[search_crawler] Link extraction error: {e}")

    # Fallback: grab all outbound links if structured selector fails
    if not links:
        print("[search_crawler] Structured selector found nothing, trying fallback")
        try:
            for a in page.query_selector_all("a[href]"):
                href = a.get_attribute("href")
                if href and href.startswith("http") and "duckduckgo.com" not in href:
                    links.append(href)
        except Exception:
            pass

    print(f"[search_crawler] Extracted {len(links)} raw links")

    queued = 0
    for link in links:
        try:
            domain = urlparse(link).netloc.lower().replace("www.", "")
        except Exception:
            continue

        if any(skip in domain for skip in SKIP_DOMAINS):
            continue
        if is_visited(link):
            continue

        if is_aggregator_site(link):
            push_aggregator(link, depth=1)
        else:
            push_crawler(link, depth=0)

        queued += 1

    print(f"[search_crawler] Queued {queued} new URLs for \"{query}\"")
    return queued

# ─── Main run ─────────────────────────────────────────────────────────────────

def run_search_crawler():
    print(f"\n[search_crawler] ── Starting run at {datetime.utcnow().isoformat()} ──")

    dynamic_queries = build_dynamic_queries()

    seen        = set()
    all_queries = []
    for q in STATIC_QUERIES + dynamic_queries:
        if q not in seen:
            seen.add(q)
            all_queries.append(q)

    print(f"[search_crawler] {len(STATIC_QUERIES)} static + {len(dynamic_queries)} dynamic = {len(all_queries)} total queries")

    total_queued = 0

    with sync_playwright() as p:
        browser, context = make_browser_context(p)
        page = context.new_page()

        for i, query in enumerate(all_queries):
            total_queued += search_duckduckgo(query, page)

            # Polite delay between queries
            time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

            # Longer cooldown every 10 queries
            if (i + 1) % 10 == 0:
                pause = random.uniform(5, 10)
                print(f"[search_crawler] Cooldown: {pause:.1f}s after {i + 1} queries")
                time.sleep(pause)

        context.close()
        browser.close()

    print(f"\n[search_crawler] ── Run complete ──")
    print(f"[search_crawler] Total URLs queued: {total_queued}")
    try:
        print(f"[search_crawler] Queue stats: {queue_stats()}")
    except Exception as e:
        print(f"[search_crawler] Could not get queue stats: {e}")

# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    run_search_crawler()

    schedule.every(12).hours.do(run_search_crawler)
    print("[search_crawler] Scheduled to run every 12 hours.")

    while True:
        schedule.run_pending()
        time.sleep(60)