"""This file is not being used anymore by docker, and was an inital test to for scraping data"""

from datetime import datetime
from playwright.sync_api import sync_playwright
from pymongo import MongoClient
from ml.ml_pipeline import process_raw_document

# MongoDB setup
client = MongoClient("mongodb://mongo:27017")
db = client["scholarshipdb"] 
raw_collection = db["raw_results"]


def scrape_page(url: str) -> dict:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Go to the page
        page.goto(url, timeout=60000)

        # Core fields we always want
        data = {
            "url": url,
            "title": page.title(),           # page title
            "text": page.inner_text("body"), # full visible text
            "scraped_at": datetime.utcnow().isoformat(),
        }

        browser.close()
        return data


if __name__ == "__main__":
    test_url = "https://example.com"
    data = scrape_page(test_url)

    # Insert raw data
    raw_id = raw_collection.insert_one(data).inserted_id

    # Fetch raw doc
    doc = raw_collection.find_one({"_id": raw_id})

    # Run ML pipeline immediately
    cleaned = process_raw_document(doc)

    print("ML pipeline output:")
    print(cleaned)
