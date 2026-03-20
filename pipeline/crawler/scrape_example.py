from datetime import datetime
from playwright.sync_api import sync_playwright
from pymongo import MongoClient

client = MongoClient("mongodb://mongo:27017")
db = client["scholarship_crawler"]
raw = db["raw_results"]



def scrape_page(url: str) -> dict:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Go to the page
        page.goto(url, timeout=60000)

        # Core fields we always want
        data = {
            "url": url,                      # ← always save the URL
            "title": page.title(),           # page title
            "text": page.inner_text("body"), # full visible text
            "scraped_at": datetime.utcnow().isoformat(),
        }

        browser.close()
        return data


if __name__ == "__main__":
    test_url = "https://example.com"
    result = scrape_page(test_url)
    print(result)
