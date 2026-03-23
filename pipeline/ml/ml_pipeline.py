from transformers import pipeline
from sentence_transformers import SentenceTransformer, util
from pymongo import MongoClient
from bson import ObjectId
import os
import uuid
import re

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

SEED_TAGS = [
    {"name": "major",       "description": "Field of study or academic major", "data_type": "String"},
    {"name": "state",       "description": "US state of residence or study",   "data_type": "String"},
    {"name": "gpa",         "description": "Minimum GPA requirement",          "data_type": "Number"},
    {"name": "ethnicity",   "description": "Ethnic or cultural background",    "data_type": "String"},
    {"name": "gender",      "description": "Gender identity requirement",      "data_type": "String"},
    {"name": "degree",      "description": "Degree level (undergraduate, graduate, etc.)", "data_type": "String"},
    {"name": "citizenship", "description": "Citizenship or residency requirement", "data_type": "String"},
    {"name": "income",      "description": "Financial need or income requirement", "data_type": "String"},
]

BLACKLISTED_TAG_NAMES = {"eligibility", "scholarship", "award", "application", "details","."}

AMOUNT_PATTERN = re.compile(
    r'(?:up\s+to\s+)?'           # optional "up to"
    r'\$[\d,]+(?:\.\d{2})?'      # dollar amount
    r'(?:\s*(?:per year|per semester|annually|\/year|award))?',
    re.IGNORECASE
)

def ensure_seed_tags():
    for tag in SEED_TAGS:
        tag_collection.update_one(
            {"name": tag["name"]},
            {"$setOnInsert": tag},
            upsert=True
        )
    return list(tag_collection.find({}))


def _classify_scholarship(text: str, threshold: float = 0.65) -> bool:
    if not text or len(text.strip()) < 100:
        return False
    labels = ["scholarship application", "educational grant application", "not related"]
    result = classifier(text[:2000], labels, multi_label=True)
    pos_labels = {"scholarship application", "educational grant application"}
    combined_score = sum(s for l, s in zip(result["labels"], result["scores"]) if l in pos_labels)
    return combined_score >= threshold


def extract_amount(text: str) -> str | None:
    match = AMOUNT_PATTERN.search(text[:3000])
    if match:
        return match.group(0).strip()

    # LLM fallback
    prompt = (
        "Extract the scholarship award amount from the text. "
        "Return only the dollar amount (e.g. '$5,000'). "
        "If not found, reply 'N/A'.\n\n"
        f"Text: {text[:600]}\n\nAmount:"
    )
    raw = generator(prompt, max_new_tokens=15)[0]["generated_text"].strip()
    raw = raw.split("\n")[0].strip()
    if any(x in raw.lower() for x in ["n/a", "none", "unknown"]):
        return None
    if not any(c.isdigit() for c in raw):
        return None
    return raw


def generate_summary(text: str) -> str:
    return summarizer(text, max_length=120, min_length=40, truncation=True)[0]["summary_text"]


def extract_tag_value(context: str, tag_name: str) -> str:
    prompt = (
        f"Extract the specific '{tag_name}' requirement from the scholarship text below. "
        f"Be concise. If not mentioned, reply 'N/A'.\n\nText: {context[:500]}\n\nValue:"
    )
    raw = generator(prompt, max_new_tokens=10)[0]["generated_text"].lower().strip()
    raw = raw.split("\n")[0].strip()
    if any(x in raw for x in ["n/a", "none", "unknown", "any", "not mentioned"]):
        return "any"
    return raw


def assign_tags(title: str, summary: str, full_text: str = "", target_count: int = 5) -> list:
    """
    Two-phase approach:
      1. Semantic similarity picks which tag TYPES are relevant to this scholarship
      2. LLM extracts the value — if it can't find one, store the tag_type name as the value
         rather than dropping the tag entirely
    """
    context_for_match  = f"{title}\n\n{summary}".strip()
    context_for_values = f"{title}\n\n{full_text[:1500]}".strip() if full_text else context_for_match

    # Always ensure seed tags exist and get them back
    existing_tags = ensure_seed_tags()

    # If for some reason the DB is still empty after seeding, create them directly
    if not existing_tags:
        print("[ml] WARNING: tag collection empty even after seeding, force-inserting")
        tag_collection.insert_many([
            {**tag, "_id": ObjectId()} for tag in SEED_TAGS
        ])
        existing_tags = list(tag_collection.find({}))

    tag_vectors = embedder.encode([t["description"] for t in existing_tags])
    summary_vec = embedder.encode(context_for_match)
    scores = util.cos_sim(summary_vec, tag_vectors)[0]

    score_list = [(existing_tags[i], float(scores[i])) for i in range(len(existing_tags))]
    score_list.sort(key=lambda x: x[1], reverse=True)

    print(f"[ml] All tag scores for '{title[:50]}':")
    for t, s in score_list:
        print(f"      {t['name']}: {round(s, 4)}")

    # Take top N by score regardless of threshold — the ranking itself is the signal
    # Filter blacklist but don't filter by score floor
    candidates = [
        (t, s) for t, s in score_list
        if t.get("name") not in BLACKLISTED_TAG_NAMES
    ][:target_count]

    assigned = []
    used_type_ids = set()

    for tag, score in candidates:
        tag_id = tag["_id"]
        if tag_id in used_type_ids:
            continue

        value = extract_tag_value(context_for_values, tag["name"])
        print(f"[ml] extract_tag_value('{tag['name']}') → {value!r}")

        # If LLM says "any"/N/A, still store the tag but with a placeholder
        # so the tag_type reference exists in the document
        if value in ("any",):
            # Only skip if score is also low — high-scoring tags get stored even without a value
            if score < 0.50:
                print(f"[ml] Skipping '{tag['name']}' — low score ({score:.3f}) and no value")
                continue
            value = "unspecified"

        assigned.append({
            "tag_type": tag_id,
            "tag_value": value,
        })
        used_type_ids.add(tag_id)

    print(f"[ml] Final: {len(assigned)} tags assigned to '{title[:50]}'")
    return assigned


def process_raw_document(doc: dict) -> dict | None:
    text = doc.get("text", "")
    if not _classify_scholarship(text):
        return None

    summary = generate_summary(text)
    amount  = extract_amount(text)                           
    tags    = assign_tags(
        title=doc.get("title", ""),
        summary=summary,
        full_text=text,                                         
    )

    print(f"[ml] amount={amount!r}  tags={len(tags)}  url={doc['url'][:60]}")

    cleaned = {
        "url":     doc["url"],
        "name":    doc.get("title", ""),
        "summary": summary,
        "tags":    tags,
        "amount":  amount,
        "date":    {"found": doc.get("scraped_at")},
        "raw_id":  doc["_id"],
    }

    clean_collection.update_one(
        {"url": doc["url"]},
        {
            "$set": cleaned,
            "$setOnInsert": {"id": str(uuid.uuid4())}
        },
        upsert=True
    )
    return cleaned