from transformers import pipeline
from sentence_transformers import SentenceTransformer, util
from pymongo import MongoClient
from bson import ObjectId
import os
import uuid

# Models
classifier = pipeline("zero-shot-classification", model="cross-encoder/nli-MiniLM2-L6-H768")
summarizer = pipeline("summarization", model="sshleifer/distilbart-cnn-6-6")
embedder   = SentenceTransformer("all-MiniLM-L6-v2")
generator  = pipeline("text2text-generation", model="google/flan-t5-large")

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://mongo:27017/scholarshipdb")
client = MongoClient(MONGO_URI)
db = client[MONGO_URI.rstrip("/").split("/")[-1] or "scholarshipdb"]

raw_collection   = db["raw_results"]
clean_collection = db["scholarships"]
tag_collection   = db["tags"]

BLACKLISTED_TAG_NAMES = {"eligibility", "scholarship", "award", "application", "details","."}

def _classify_scholarship(text: str, threshold: float = 0.65) -> bool:
    """Aggregates scores across multiple positive labels for better recall."""
    if not text or len(text.strip()) < 100: return False
    
    # Expanded label set to catch nuances
    labels = ["scholarship application", "educational grant", "financial aid details", "not related"]
    result = classifier(text[:2000], labels, multi_label=True)
    
    pos_labels = ["scholarship application", "educational grant", "financial aid details"]
    combined_score = sum(s for l, s in zip(result["labels"], result["scores"]) if l in pos_labels)
    
    return combined_score >= threshold

def generate_summary(text: str) -> str:
    return summarizer(text, max_length=120, min_length=40, truncation=True)[0]["summary_text"]

def extract_tag_value(context: str, tag_name: str) -> str:
    """Uses a more restrictive prompt to prevent model hallucinations."""
    prompt = (
        f"Extract the specific '{tag_name}' requirement from the text below. "
        f"If not mentioned, reply 'N/A'.\n\nText: {context[:500]}\n\nValue:"
    )
    raw = generator(prompt, max_new_tokens=10)[0]["generated_text"].lower().strip()
    if any(x in raw for x in ["n/a", "none", "unknown", "any"]):
        return "any"
    return raw

def assign_tags(title: str, summary: str, target_count: int = 5) -> list:
    context = f"{title}\n\n{summary}".strip()
    existing_tags = list(tag_collection.find({}))
    assigned = []
    used_type_ids = set()

    if existing_tags:
        tag_vectors = embedder.encode([t["description"] for t in existing_tags])
        summary_vec = embedder.encode(context)
        scores = util.cos_sim(summary_vec, tag_vectors)[0]

        matches = sorted(
            [(existing_tags[i], float(scores[i])) for i in range(len(existing_tags))
             if float(scores[i]) >= 0.70], # Stricter threshold
            key=lambda x: x[1], reverse=True
        )

        for tag, _ in matches[:target_count]:
            if tag["_id"] not in used_type_ids:
                assigned.append({"tag_type": tag["_id"], "tag_value": extract_tag_value(context, tag["name"])})
                used_type_ids.add(tag["_id"])

    return assigned

def process_raw_document(doc: dict) -> dict | None:
    text = doc.get("text", "")
    if not _classify_scholarship(text): return None

    summary = generate_summary(text)
    tags = assign_tags(title=doc.get("title", ""), summary=summary)

    cleaned = {
        "url": doc["url"],
        "name": doc.get("title", ""),
        "summary": summary,
        "tags": tags,
        "date": {"found": doc.get("scraped_at")},
        "raw_id": doc["_id"],
    }

    clean_collection.update_one({"url": doc["url"]}, {"$set": cleaned, "$setOnInsert": {"id": str(uuid.uuid4())}}, upsert=True)
    return cleaned