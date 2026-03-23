from transformers import pipeline
from sentence_transformers import SentenceTransformer, util
from pymongo import MongoClient
from bson import ObjectId
import os
import uuid

# ─── Models ───────────────────────────────────────────────────────────────────

classifier = pipeline("zero-shot-classification", model="cross-encoder/nli-MiniLM2-L6-H768")
summarizer = pipeline("summarization", model="sshleifer/distilbart-cnn-6-6")
embedder   = SentenceTransformer("all-MiniLM-L6-v2")
generator  = pipeline("text2text-generation", model="google/flan-t5-large")

print("[ml] Models loaded successfully")

# ─── MongoDB ───────────────────────────────────────────────────────────────────

# Respect the MONGO_URI environment variable set in docker-compose
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://mongo:27017/scholarshipdb")
client = MongoClient(MONGO_URI)

# Parse the DB name from the URI, default to "scholarshipdb"
_db_name = MONGO_URI.rstrip("/").split("/")[-1] or "scholarshipdb"
db = client[_db_name]

raw_collection   = db["raw_results"]
clean_collection = db["scholarships"]
tag_collection   = db["tags"]

# ─── Constants ────────────────────────────────────────────────────────────────

BLACKLISTED_TAG_NAMES = {
    "eligibility", "requirement", "criteria", "scholarship", "award",
    "financial", "aid", "application", "information", "details",
    "description", "type", "category", "other", "general", "misc",
    "various", "multiple", "any", "none", "unknown", "n/a",
}

SCHOLARSHIP_KEYWORDS = {
    "apply", "eligible", "eligibility", "award", "grant",
    "deadline", "submit", "recipient", "scholarship",
}


# ─── Scholarship verification ─────────────────────────────────────────────────

def _classify_scholarship(text: str, min_length: int = 50, threshold: float = 0.75) -> bool:
    """Return True if the text looks like a scholarship page."""
    if not text or len(text.strip()) < min_length:
        return False
    if not text.startswith("Summary: "):
        if not any(kw in text.lower() for kw in SCHOLARSHIP_KEYWORDS):
            return False
    labels = ["scholarship application page", "not a scholarship"]
    result = classifier(text[:3000], labels)
    return (
        result["labels"][0] == "scholarship application page"
        and result["scores"][0] >= threshold
    )


def verify_scholarship(raw_text: str, summary: str | None = None) -> bool:
    """
    Two-stage check:
      1. Raw page text must pass.
      2. If a summary is provided, it must also pass.
    """
    if not _classify_scholarship(raw_text):
        return False
    if summary is not None and not _classify_scholarship(
        "Summary: " + summary, min_length=10
    ):
        return False
    return True


# ─── Summarization ────────────────────────────────────────────────────────────

def generate_summary(text: str) -> str:
    result = summarizer(
        text,
        max_length=120,
        min_length=40,
        truncation=True,
    )[0]["summary_text"]
    return result


# ─── Tag helpers ──────────────────────────────────────────────────────────────

def _clean_generated(text: str, max_len: int = 30) -> str:
    """Strip artefacts from small model output and normalise."""
    text = text.split("\n")[-1].strip().lower()
    for prefix in ("the ", "a ", "an ", "is ", "are ", "for "):
        if text.startswith(prefix):
            text = text[len(prefix):]
    return text if text and len(text) <= max_len else ""


def extract_tag_value(context: str, tag_name: str) -> str:
    """Extract a specific value for a known tag type from the scholarship context."""
    prompt = (
        f"For the scholarship below, what is the specific '{tag_name}' requirement?\n"
        f"Reply with only 1-3 words. Examples:\n"
        f"  - tag 'major' → 'computer science'\n"
        f"  - tag 'state' → 'california'\n"
        f"  - tag 'gpa' → '3.5'\n"
        f"  - tag 'gender' → 'female'\n"
        f"  - tag 'race' → 'hispanic'\n\n"
        f"Scholarship: {context[:400]}\n\n"
        f"Value for '{tag_name}':"
    )
    raw = generator(prompt, max_new_tokens=10)[0]["generated_text"]

    if f"Value for '{tag_name}':" in raw:
        raw = raw.split(f"Value for '{tag_name}':")[-1]

    result = _clean_generated(raw, max_len=40)
    return result or "any"


def create_tag_with_value(context: str, hint: str = "") -> dict | None:
    type_prompt = (
        (f"{hint}\n\n" if hint else "") +
        "What is one specific eligibility requirement category for this scholarship? "
        "Reply with only 1-2 words like 'race', 'major', 'state', 'gpa', 'religion', 'gender', 'disability'.\n\n"
        f"Scholarship: {context[:300]}"
    )
    raw_name = generator(type_prompt, max_new_tokens=8)[0]["generated_text"]
    tag_name = _clean_generated(raw_name)

    if not tag_name or tag_name in BLACKLISTED_TAG_NAMES:
        return None

    tag_value = extract_tag_value(context, tag_name)

    desc_prompt = (
        f"In one or two sentences, describe what '{tag_name}' means as a scholarship eligibility filter."
    )
    raw_desc = generator(desc_prompt, max_new_tokens=30)[0]["generated_text"].strip()
    tag_desc = raw_desc.split("\n")[-1].strip() or f"Eligibility requirement: {tag_name}"

    existing = tag_collection.find_one({"name": tag_name})
    if existing:
        return {"tag_type": existing, "tag_value": tag_value}

    tag_doc = {
        "_id":       ObjectId(),
        "name":      tag_name,
        "description": tag_desc,
        "data_type": "String",
    }
    tag_collection.insert_one(tag_doc)
    return {"tag_type": tag_doc, "tag_value": tag_value}


# ─── Multi-tag assignment ─────────────────────────────────────────────────────

def assign_tags(title: str, summary: str, target_count: int = 5) -> list:
    """
    Assign tags to a scholarship.

    FIX: 'title' is now an explicit parameter instead of a free variable.
    Reuses existing tag types by semantic similarity, creates new ones to fill slots.
    Returns a list of {"tag_type": ObjectId, "tag_value": str}.
    """
    context = f"{title}\n\n{summary}".strip() if title else summary

    existing_tags = list(tag_collection.find({}))
    assigned = []
    used_type_ids = set()

    # Step 1: Match existing tag types by semantic similarity
    if existing_tags:
        tag_descriptions = [t["description"] for t in existing_tags]
        tag_vectors  = embedder.encode(tag_descriptions)
        summary_vec  = embedder.encode(context)
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
                value = extract_tag_value(context, tag["name"])
                assigned.append({"tag_type": tag["_id"], "tag_value": value})
                used_type_ids.add(tag["_id"])

    # Step 2: Generate new specific tags for remaining slots
    title_hint = f"Scholarship title: '{title}'\n" if title else ""

    angles = [
        f"{title_hint}Who is eligible based on race, ethnicity, or national background?",
        f"{title_hint}What field of study or academic major is required?",
        f"{title_hint}What U.S. state, region, or location is required?",
        f"{title_hint}What GPA, grade level, or academic standing is needed?",
        f"{title_hint}What specific demographic qualifier exists (gender, religion, disability, income)?",
        f"{title_hint}What career path or professional industry is this scholarship targeting?",
    ]

    angle_index  = 0
    max_attempts = target_count * 4
    attempts     = 0

    while len(assigned) < target_count and attempts < max_attempts:
        angle = angles[angle_index % len(angles)]
        angle_index += 1
        attempts += 1

        result = create_tag_with_value(context, hint=angle)
        if result is None:
            continue

        type_id = result["tag_type"]["_id"]
        if type_id not in used_type_ids:
            assigned.append({"tag_type": type_id, "tag_value": result["tag_value"]})
            used_type_ids.add(type_id)

    return assigned


# ─── Full pipeline for one raw document ───────────────────────────────────────

def process_raw_document(doc: dict) -> dict | None:
    text  = doc.get("text", "")
    title = doc.get("title", "")

    # Step 1: loose check on raw text
    if not _classify_scholarship(text, threshold=0.70):
        print(f"[ml] Skipping non-scholarship page: {doc['url']}")
        return None

    # Step 2: summarise
    summary = generate_summary(text)

    # Step 3: strict check on clean summary
    if not _classify_scholarship("Summary: " + summary, min_length=10, threshold=0.80):
        print(f"[ml] Summary failed verification, skipping: {doc['url']}")
        return None

    # Step 4: assign tags — pass title explicitly (fixes scoping bug)
    tags = assign_tags(title=title, summary=summary, target_count=5)

    # Step 5: build cleaned document
    # Store tags with just the ObjectId reference (not the full tag doc)
    cleaned_tags = []
    for t in tags:
        tag_type = t["tag_type"]
        type_id  = tag_type["_id"] if isinstance(tag_type, dict) else tag_type
        cleaned_tags.append({"tag_type": type_id, "tag_value": t["tag_value"]})

    cleaned = {
        "url":     doc["url"],
        "name":    title,
        "summary": summary,
        "tags":    cleaned_tags,
        "date":    {"found": doc.get("scraped_at")},
        "raw_id":  doc["_id"],
    }

    clean_collection.update_one(
        {"url": doc["url"]},
        {
            "$set":         cleaned,
            "$setOnInsert": {"id": str(uuid.uuid4())},
        },
        upsert=True,
    )

    return cleaned


# ─── Batch processing ─────────────────────────────────────────────────────────

def process_all_raw():
    for doc in raw_collection.find({}):
        process_raw_document(doc)