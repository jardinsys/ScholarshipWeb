from transformers import pipeline
from sentence_transformers import SentenceTransformer, util
from pymongo import MongoClient
from bson import ObjectId
import uuid

# Load ML models
# Scholarship verification (zero-shot classifier)
classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")

# Summarization
summarizer = pipeline("summarization", model="sshleifer/distilbart-cnn-12-6")

# Embeddings for tag matching
embedder = SentenceTransformer("all-MiniLM-L6-v2")

# Tag creation (generative)
generator = pipeline("text2text-generation", model="google/flan-t5-large")

print("[ml] Models loaded successfully")

# MongoDB setup
client = MongoClient("mongodb://mongo:27017")
db = client["scholarshipdb"]  # shared DB with frontend

raw_collection   = db["raw_results"]
clean_collection = db["scholarships"]
tag_collection   = db["tags"]

# Tags too generic to ever be useful
BLACKLISTED_TAG_NAMES = {
    "eligibility", "requirement", "criteria", "scholarship", "award",
    "financial", "aid", "application", "information", "details",
    "description", "type", "category", "other", "general", "misc",
    "various", "multiple", "any", "none", "unknown", "n/a",
}


# Scholarship verification
def _classify_scholarship(text: str, min_length: int = 50) -> bool:
    """Return True if the text looks like a scholarship page (score >= 0.85)."""
    if not text or len(text.strip()) < min_length:
        return False
    labels = ["scholarship opportunity", "not a scholarship"]
    result = classifier(text[:1000], labels)  # cap length for speed
    return result["labels"][0] == "scholarship opportunity" and result["scores"][0] >= 0.85


def verify_scholarship(raw_text: str, summary: str | None = None) -> bool:
    """
    Two-stage check:
      1. Raw page text must pass.
      2. If a summary is provided, it must also pass (catches login walls,
         listing pages, etc. that slip through on raw text alone).
    """
    if not _classify_scholarship(raw_text):
        return False
    if summary is not None and not _classify_scholarship(summary, min_length=20):
        return False
    return True


# Summarization 
def generate_summary(text: str) -> str:
    result = summarizer(
        text,
        max_length=120,
        min_length=40,
        truncation=True,
    )[0]["summary_text"]
    return result


# Tag helpers 
def _clean_generated(text: str, max_len: int = 30) -> str:
    """Strip artefacts from small model output and normalise."""
    text = text.split("\n")[-1].strip().lower()
    # remove leading punctuation / filler words the model sometimes prepends
    for prefix in ("the ", "a ", "an ", "is ", "are ", "for "):
        if text.startswith(prefix):
            text = text[len(prefix):]
    return text if text and len(text) <= max_len else ""


def extract_tag_value(summary: str, tag_name: str) -> str:
    prompt = (
        f"What is the specific value for '{tag_name}' in this scholarship? "
        f"Reply with only 1-3 words.\n\n"
        f"Scholarship: {summary[:300]}"
    )
    raw = generator(prompt, max_new_tokens=8)[0]["generated_text"].strip().lower()
    result = _clean_generated(raw)
    return result or "any"


def create_tag_with_value(summary: str, hint: str = "") -> dict | None:
    """
    Generate a new tag type + value from the summary.
    Returns None if the generated name is blacklisted or too vague.
    """
    type_prompt = (
        (f"{hint}\n\n" if hint else "") +
        "What is one specific eligibility requirement category for this scholarship? "
        "Reply with only 1-2 words like 'race', 'major', 'state', 'gpa', 'religion', 'gender', 'disability'.\n\n"
        f"Scholarship: {summary[:300]}"
    )
    raw_name = generator(type_prompt, max_new_tokens=8)[0]["generated_text"]
    tag_name = _clean_generated(raw_name)

    # Reject blacklisted / empty names immediately
    if not tag_name or tag_name in BLACKLISTED_TAG_NAMES:
        return None

    value_prompt = (
        f"What is the specific value for '{tag_name}' in this scholarship? "
        f"Reply with only 1-3 words.\n\n"
        f"Scholarship: {summary[:300]}"
    )
    raw_value = generator(value_prompt, max_new_tokens=8)[0]["generated_text"]
    tag_value = _clean_generated(raw_value, max_len=40) or "see description"

    desc_prompt = (
        f"In one sentence, describe what '{tag_name}' means as a scholarship eligibility filter."
    )
    raw_desc = generator(desc_prompt, max_new_tokens=30)[0]["generated_text"].strip()
    tag_desc = raw_desc.split("\n")[-1].strip() or f"Eligibility requirement: {tag_name}"

    # Reuse existing tag type if name already exists
    existing = tag_collection.find_one({"name": tag_name})
    if existing:
        return {"tag_type": existing, "tag_value": tag_value}

    tag_doc = {
        "_id": ObjectId(),
        "name": tag_name,
        "description": tag_desc,
        "data_type": "String",
    }
    tag_collection.insert_one(tag_doc)
    return {"tag_type": tag_doc, "tag_value": tag_value}


# Multi-tag assignment 
def assign_tags(summary: str, target_count: int = 5) -> list:
    """
    Assign tags to a scholarship.
    - Reuse existing tag types whose description semantically matches.
    - Create new specific tag types to fill remaining slots.
    Returns a list of {"tag_type": ObjectId, "tag_value": str}.
    """
    existing_tags = list(tag_collection.find({}))
    assigned = []
    used_type_ids = set()

    # Step 1: Match existing tag types by semantic similarity
    if existing_tags:
        tag_descriptions = [t["description"] for t in existing_tags]
        tag_vectors  = embedder.encode(tag_descriptions)
        summary_vec  = embedder.encode(summary)
        scores = util.cos_sim(summary_vec, tag_vectors)[0]

        matches = sorted(
            [
                (existing_tags[i], float(scores[i]))
                for i in range(len(existing_tags))
                if float(scores[i]) >= 0.50
                and existing_tags[i]["name"] not in BLACKLISTED_TAG_NAMES
            ],
            key=lambda x: x[1],
            reverse=True,
        )

        for tag, _score in matches[:target_count]:
            if tag["_id"] not in used_type_ids:
                value = extract_tag_value(summary, tag["name"])
                assigned.append({"tag_type": tag["_id"], "tag_value": value})
                used_type_ids.add(tag["_id"])

    # Step 2: Generate new specific tags for remaining slots
    angles = [
        "Who is eligible based on race, ethnicity, or national background?",
        "What field of study or academic major is required?",
        "What U.S. state, region, or location is required?",
        "What GPA, grade level, or academic standing is needed?",
        "What specific demographic qualifier exists (gender, religion, disability, income)?",
        "What career path or professional industry is this scholarship targeting?",
    ]

    angle_index = 0
    max_attempts = target_count * 4
    attempts = 0

    while len(assigned) < target_count and attempts < max_attempts:
        angle = angles[angle_index % len(angles)]
        angle_index += 1
        attempts += 1

        result = create_tag_with_value(summary, hint=angle)
        if result is None:
            continue  # blacklisted name — try a different angle

        type_id = result["tag_type"]["_id"]
        if type_id not in used_type_ids:
            assigned.append({"tag_type": type_id, "tag_value": result["tag_value"]})
            used_type_ids.add(type_id)

    return assigned


# Full pipeline for one raw document 
def process_raw_document(doc: dict) -> dict | None:
    text = doc.get("text", "")

    # Step 1: Quick text-only check (fast reject before summarising)
    if not _classify_scholarship(text):
        print(f"[ml] Skipping non-scholarship page: {doc['url']}")
        return None

    # Step 2: Summarise
    summary = generate_summary(text)

    # Step 3: Verify again using the summary (catches login walls / listing pages)
    if not _classify_scholarship(summary, min_length=20):
        print(f"[ml] Summary failed verification, skipping: {doc['url']}")
        return None

    # Step 4: Assign tags
    tags = assign_tags(summary, target_count=4)

    # Step 5: Build cleaned document
    cleaned = {
        "url":     doc["url"],
        "name":    doc.get("title", ""),
        "summary": summary,
        "tags":    tags,
        "date": {
            "found": doc.get("scraped_at"),
        },
        "raw_id":  doc["_id"],
    }

    # Upsert by URL; $setOnInsert ensures id is only written once on initial insert
    # and never overwritten on subsequent updates to the same URL.
    clean_collection.update_one(
        {"url": doc["url"]},
        {
            "$set":         cleaned,
            "$setOnInsert": {"id": str(uuid.uuid4())},
        },
        upsert=True,
    )

    return cleaned


# Batch processing 
def process_all_raw():
    for doc in raw_collection.find({}):
        process_raw_document(doc)