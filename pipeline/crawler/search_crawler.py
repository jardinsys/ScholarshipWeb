"""
search_crawler.py — Bing-based active search crawler

Searches Bing for scholarship-related queries and feeds discovered URLs
into the existing worker queue for the ML pipeline to process.

Query sources:
  1. Static seed queries  — broad terms always worth searching
  2. Dynamic queries      — built from tag names + values already in MongoDB
                            e.g. tag "major: computer science" → "computer science scholarship"

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

# Realistic browser user agent — reduces chance of Bing serving a bot page
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

# Domains to skip — search engines, social media, irrelevant noise
SKIP_DOMAINS = {
    "bing.com", "google.com", "facebook.com", "twitter.com", "x.com",
    "instagram.com", "youtube.com", "linkedin.com", "reddit.com",
    "wikipedia.org", "amazon.com", "ebay.com", "pinterest.com",
    "tiktok.com", "snapchat.com", "microsoft.com", "apple.com",
}

# How many Bing result pages to paginate per query (each = ~10 results)
PAGES_PER_QUERY = 3

# Polite delay range between requests (seconds) — randomised to look human
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
    """
    Build search queries from tag names and scholarship tag values in MongoDB.

    Strategy:
      - Tag names   → "{tag_name} scholarship"
                      e.g. "major scholarship", "state scholarship"
      - Tag values  → "{tag_value} scholarship"
                      e.g. "computer science scholarship", "california scholarship"
    """
    queries = []
    seen    = set()

    def add(q: str):
        q = q.strip().lower()
        if q and q not in seen and len(q) > 5:
            seen.add(q)
            queries.append(q)

    try:
        # From tag type names
        for tag in tag_collection.find({}):
            name = tag.get("name", "").strip()
            if name:
                add(f"{name} scholarship")

        # From distinct tag values across all scholarships
        pipeline = [
            {"$unwind": "$tags"},
            {"$group": {"_id": "$tags.tag_value"}},
            {"$limit": 150},
        ]
        for doc in scholarship_collection.aggregate(pipeline):
            val = str(doc.get("_id", "")).strip()
            if val and val.lower() != "any" and len(val) > 2:
                add(f"{val} scholarship")

    except Exception as e:
        print(f"[search_crawler] Warning: could not build dynamic queries: {e}")

    print(f"[search_crawler] Built {len(queries)} dynamic queries from MongoDB")
    return queries


# ─── Bing result link extractor ───────────────────────────────────────────────

def extract_bing_links(page) -> list[str]:
    """
    Extract organic result links from a Bing search results page.
    Bing wraps results in <li class="b_algo"> with an <h2><a href=...>.
    Falls back to any outbound <a> if the structured selector finds nothing.
    """
    urls = []

    # Primary: structured Bing result links
    try:
        anchors = page.query_selector_all("li.b_algo h2 a")
        for a in anchors:
            href = a.get_attribute("href")
            if href and href.startswith("http"):
                urls.append(href)
    except Exception:
        pass

    # Fallback: all outbound links on the page
    if not urls:
        try:
            for a in page.query_selector_all("a[href]"):
                href = a.get_attribute("href")
                if href and href.startswith("http") and "bing.com" not in href:
                    urls.append(href)
        except Exception:
            pass

    return urls


# ─── Search one query on Bing ─────────────────────────────────────────────────

def search_bing(query: str, page) -> int:
    """
    Search Bing for `query`, paginate through PAGES_PER_QUERY result pages,
    and push discovered URLs into the appropriate Redis queue.
    Returns the number of new URLs queued.
    """
    total_queued = 0

    for page_num in range(PAGES_PER_QUERY):
        # Bing pagination uses `first` param: 1, 11, 21 ...
        first = page_num * 10 + 1
        url   = f"https://www.bing.com/search?q={quote_plus(query)}&count=10&first={first}"

        print(f"[search_crawler] Bing p{page_num + 1}: \"{query}\"")

        try:
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
        except Exception as e:
            print(f"[search_crawler] Failed to load Bing results: {e}")
            break

        # Detect CAPTCHA / bot challenge
        try:
            body_text = page.inner_text("body")
        except Exception:
            body_text = ""

        if "captcha" in body_text.lower() or "verify you are a human" in body_text.lower():
            print("[search_crawler] ⚠ Bing CAPTCHA detected — pausing 60s")
            time.sleep(60)
            break

        links = extract_bing_links(page)

        if not links:
            print(f"[search_crawler] No results on page {page_num + 1}, stopping")
            break

        queued_this_page = 0
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

            queued_this_page += 1

        total_queued += queued_this_page
        print(f"[search_crawler] Queued {queued_this_page} URLs from page {page_num + 1}")

    return total_queued


# Main run
def run_search_crawler():
    print(f"\n[search_crawler] ── Starting run at {datetime.utcnow().isoformat()} ──")

    dynamic_queries = build_dynamic_queries()

    # Merge static + dynamic, deduplicate, static goes first
    seen        = set()
    all_queries = []
    for q in STATIC_QUERIES + dynamic_queries:
        if q not in seen:
            seen.add(q)
            all_queries.append(q)

    print(f"[search_crawler] {len(STATIC_QUERIES)} static + {len(dynamic_queries)} dynamic = {len(all_queries)} total queries")

    total_queued = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=USER_AGENT)
        page    = context.new_page()

        for i, query in enumerate(all_queries):
            total_queued += search_bing(query, page)

            # Longer cooldown every 10 queries to avoid rate limiting
            if (i + 1) % 10 == 0:
                pause = random.uniform(5, 10)
                print(f"[search_crawler] Cooldown: {pause:.1f}s after {i + 1} queries")
                time.sleep(pause)

        context.close()
        browser.close()

    print(f"\n[search_crawler] ── Run complete ──")
    print(f"[search_crawler] Total URLs queued: {total_queued}")
    print(f"[search_crawler] Queue stats: {queue_stats()}")


# Entry point 
if __name__ == "__main__":
    run_search_crawler()

    schedule.every(12).hours.do(run_search_crawler)
    print("[search_crawler] Scheduled to run every 12 hours.")

    while True:
        schedule.run_pending()
        time.sleep(60)