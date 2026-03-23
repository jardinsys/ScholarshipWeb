import redis

VISITED_EXPIRY_SECONDS = 7 * 24 * 60 * 60  # 7 days
MAX_DEPTH = 4  # maximum crawl depth from seed URL

r = redis.Redis(host="redis", port=6379, decode_responses=True)


# Aggregator Sites 
def add_aggregator_site(url: str):
    """Add a site to the known aggregator set."""
    r.rpush("aggregator:sites", url)

def get_aggregator_sites() -> set:
    """Get all known aggregator sites."""
    return r.lrange("aggregator:sites", 0, -1)

def is_aggregator_site(url: str) -> bool:
    """Check if a URL's domain matches a known aggregator site."""
    from urllib.parse import urlparse
    domain = urlparse(url).netloc
    for site in get_aggregator_sites():
        if domain in site:
            return True
    return False


# Queues 
def push_aggregator(url: str, depth: int = 0):
    """Push a URL onto the aggregator queue."""
    if depth > MAX_DEPTH:
        return
    if is_visited(url):
        return
    r.lpush("queue:aggregator", f"{depth}|{url}")

def push_crawler(url: str, depth: int = 0):
    """Push a URL onto the general crawler queue."""
    if depth > MAX_DEPTH:
        return
    if is_visited(url):
        return
    r.lpush("queue:crawler", f"{depth}|{url}")

def pop_aggregator() -> tuple[str, int] | None:
    """Pop the next URL from the aggregator queue. Returns (url, depth) or None."""
    item = r.rpop("queue:aggregator")
    if item is None:
        return None
    depth, url = item.split("|", 1)
    return url, int(depth)

def pop_crawler() -> tuple[str, int] | None:
    """
    Pop the next URL to crawl.
    Prioritizes aggregator queue, falls back to crawler queue.
    Returns (url, depth) or None.
    """
    item = r.rpop("queue:aggregator") or r.rpop("queue:crawler")
    if item is None:
        return None
    depth, url = item.split("|", 1)
    return url, int(depth)


# Visited URLs 
def mark_visited(url: str):
    """Mark a URL as visited with a 7 day expiry."""
    r.setex(f"visited:{url}", VISITED_EXPIRY_SECONDS, 1)

def is_visited(url: str) -> bool:
    """Check if a URL has already been visited."""
    return r.exists(f"visited:{url}") == 1


# Queue Stats (monitoring) 
def queue_stats() -> dict:
    return {
        "aggregator_queue": r.llen("queue:aggregator"),
        "crawler_queue": r.llen("queue:crawler"),
        "aggregator_sites": r.scard("aggregator:sites"),
    }