# pipeline/ml/ml_pipeline.py
#
# CHANGES FROM ORIGINAL:
#   - extract_name()       → proper scholarship name via LLM, not just page title
#   - extract_provider()   → new — who is offering the scholarship
#   - detect_essay()       → new — keyword scan for essay requirement
#   - extract_dates()      → new — deadline (date.due) and date.created via regex + LLM fallback
#   - description field    → new — cleaned excerpt of the raw text (~800 chars)
#   - assign_tags()        → now guarantees MIN_TAGS (4) assigned;
#                            auto-creates a new tag type if no existing type fits
#
# Everything else (classifier, summarizer, embedder, amount extraction) is unchanged.

from transformers import pipeline
from sentence_transformers import SentenceTransformer, util
from pymongo import MongoClient
from bson import ObjectId
import os
import uuid
import re
from datetime import datetime

# ── Models (same as before) ───────────────────────────────────────────────────

classifier = pipeline("zero-shot-classification", model="cross-encoder/nli-MiniLM2-L6-H768")
summarizer = pipeline("summarization", model="sshleifer/distilbart-cnn-6-6")
embedder   = SentenceTransformer("all-MiniLM-L6-v2")
generator  = pipeline("text2text-generation", model="google/flan-t5-large")

# ── DB setup (same as before) ─────────────────────────────────────────────────

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://mongo:27017/scholarshipdb")
client = MongoClient(MONGO_URI)
db = client[MONGO_URI.rstrip("/").split("/")[-1] or "scholarshipdb"]

raw_collection   = db["raw_results"]
clean_collection = db["scholarships"]
tag_collection   = db["tags"]

SEED_TAGS = [
    {"name": "major",       "description": "Field of study or academic major",              "data_type": "String"},
    {"name": "state",       "description": "US state of residence or study",                "data_type": "String"},
    {"name": "gpa",         "description": "Minimum GPA requirement",                       "data_type": "Number"},
    {"name": "ethnicity",   "description": "Ethnic or cultural background",                 "data_type": "String"},
    {"name": "gender",      "description": "Gender identity requirement",                   "data_type": "String"},
    {"name": "degree",      "description": "Degree level (undergraduate, graduate, etc.)", "data_type": "String"},
    {"name": "citizenship", "description": "Citizenship or residency requirement",          "data_type": "String"},
    {"name": "income",      "description": "Financial need or income requirement",          "data_type": "String"},
    # New seeds that commonly appear on scholarship pages
    {"name": "enrollment",  "description": "Full-time or part-time enrollment status",     "data_type": "String"},
    {"name": "age",         "description": "Age requirement or range",                     "data_type": "String"},
    {"name": "military",    "description": "Military affiliation or veteran status",        "data_type": "String"},
    {"name": "disability",  "description": "Disability or medical condition requirement",   "data_type": "String"},
]

BLACKLISTED_TAG_NAMES = {"eligibility", "scholarship", "award", "application", "details", "."}

# Guaranteed minimum number of tags per scholarship.
# If fewer are found via semantic matching, new tag types are auto-created.
MIN_TAGS = 4

# Regex
AMOUNT_PATTERN = re.compile(
    r'(?:up\s+to\s+)?'
    r'\$[\d,]+(?:\.\d{2})?'
    r'(?:\s*(?:per year|per semester|annually|\/year|award))?',
    re.IGNORECASE
)

# Matches common deadline phrasings, e.g.:
#   "deadline: march 15, 2025"   "due by april 1"   "apply by 12/31/2024"
DATE_DUE_PATTERN = re.compile(
    r'(?:deadline[:\s]*|due\s+(?:date[:\s]*)?|apply\s+by[:\s]*|applications?\s+due[:\s]*)'
    r'(\w+\.?\s+\d{1,2}(?:st|nd|rd|th)?,?\s*\d{4}|\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})',
    re.IGNORECASE
)

# Matches established / created dates, e.g.:
#   "established in 2010"   "founded 1999"   "since 2005"
DATE_CREATED_PATTERN = re.compile(
    r'(?:established|founded|since|created)\s+(?:in\s+)?(\d{4})',
    re.IGNORECASE
)

# Keywords that indicate an essay is NOT required
NO_ESSAY_PHRASES = [
    "no essay", "no essay required", "essay not required",
    "no writing sample", "no personal statement required",
]

# Keywords that confirm an essay IS required
ESSAY_REQUIRED_PHRASES = [
    "essay required", "personal statement required", "writing sample required",
    "submit an essay", "essay of ", "500-word essay", "250-word",
    "short essay", "long essay", "applicants must write",
]


# ── Helper: LLM single-line extraction 
def _llm_extract(prompt: str, max_tokens: int = 20) -> str:
    """Run a flan-t5 prompt and return a cleaned single-line answer."""
    raw = generator(prompt, max_new_tokens=max_tokens)[0]["generated_text"].strip()
    return raw.split("\n")[0].strip()


# Extract scholarship name (replaces bare page title)
def extract_name(title: str, text: str) -> str:
    """
    The page <title> is often a generic site title like 'Scholarships | FASTWEB'.
    We ask the LLM to pull out the actual scholarship name from the body text.
    Falls back to the raw title if the LLM can't find one.
    """
    prompt = (
        "What is the name of the scholarship described in this text? "
        "Return only the scholarship name, nothing else. "
        "If not clear, return 'Unknown Scholarship'.\n\n"
        f"Title: {title}\nText: {text[:400]}\n\nScholarship name:"
    )
    result = _llm_extract(prompt, max_tokens=25)
    if not result or result.lower() in ("unknown", "none", "n/a"):
        return title  # fallback to page title
    return result


# Extract provider / sponsoring organisation
def extract_provider(text: str) -> str | None:
    """
    Who is offering the scholarship?  E.g. 'Gates Foundation', 'NASA', 'Coca-Cola'.
    First tries a regex for common phrasing, then falls back to the LLM.
    """
    # Common phrasings: "offered by X", "sponsored by X", "provided by X", "from X"
    pattern = re.compile(
        r'(?:offered|sponsored|funded|provided|presented|awarded)\s+by\s+([A-Z][^\.\n,]{3,60})',
        re.IGNORECASE
    )
    match = pattern.search(text[:3000])
    if match:
        candidate = match.group(1).strip()
        # Sanity-check: reject suspiciously long or generic strings
        if len(candidate) < 80 and candidate.lower() not in ("the", "a", "an"):
            return candidate

    # LLM fallback
    prompt = (
        "Who is offering or sponsoring this scholarship? "
        "Return only the organisation or company name. "
        "If not found, reply 'N/A'.\n\n"
        f"Text: {text[:600]}\n\nProvider:"
    )
    result = _llm_extract(prompt, max_tokens=20)
    if result.lower() in ("n/a", "none", "unknown", "not mentioned"):
        return None
    return result


# Detect essay requirement
def detect_essay_required(text: str) -> bool | None:
    """
    Returns True  → essay required
            False → no essay required
            None  → couldn't determine (schema accepts Boolean, so we omit it)

    Strategy: keyword scan first (fast, reliable), LLM only as tiebreaker.
    """
    lower = text[:5000].lower()

    no_essay  = any(phrase in lower for phrase in NO_ESSAY_PHRASES)
    has_essay = any(phrase in lower for phrase in ESSAY_REQUIRED_PHRASES)

    if no_essay and not has_essay:
        return False
    if has_essay and not no_essay:
        return True
    if has_essay and no_essay:
        # Contradictory signals — ask the LLM
        prompt = (
            "Does this scholarship require an essay or personal statement? "
            "Answer only 'yes' or 'no'.\n\n"
            f"Text: {text[:800]}\n\nAnswer:"
        )
        answer = _llm_extract(prompt, max_tokens=5).lower()
        if "yes" in answer:
            return True
        if "no" in answer:
            return False

    return None  # unknown — will be omitted from the document


# Extract deadline and created dates 
def extract_dates(text: str) -> dict:
    """
    Returns a dict with keys 'due' and/or 'created' as ISO strings (or absent).

    date.due     → application deadline
    date.created → when the scholarship programme was established
    """
    dates = {}

    # ── deadline ──
    match = DATE_DUE_PATTERN.search(text[:5000])
    if match:
        raw_date = match.group(1).strip()
        try:
            # Try several common formats
            for fmt in ("%B %d, %Y", "%b %d, %Y", "%m/%d/%Y", "%m-%d-%Y",
                        "%B %d %Y", "%b %d %Y", "%m/%d/%y"):
                try:
                    dates["due"] = datetime.strptime(raw_date, fmt).isoformat()
                    break
                except ValueError:
                    continue
        except Exception:
            pass

    if "due" not in dates:
        # LLM fallback for deadline
        prompt = (
            "What is the application deadline for this scholarship? "
            "Reply only with the date in YYYY-MM-DD format. "
            "If not mentioned, reply 'N/A'.\n\n"
            f"Text: {text[:800]}\n\nDeadline:"
        )
        result = _llm_extract(prompt, max_tokens=15)
        if result.lower() not in ("n/a", "none", "unknown") and re.match(r"\d{4}-\d{2}-\d{2}", result):
            dates["due"] = result

    # ── established / created ──
    match = DATE_CREATED_PATTERN.search(text[:5000])
    if match:
        year = int(match.group(1))
        if 1900 < year <= datetime.now().year:
            dates["created"] = datetime(year, 1, 1).isoformat()

    return dates


# Unchanged helpers 
def ensure_seed_tags():
    for tag in SEED_TAGS:
        tag_collection.update_one(
            {"name": tag["name"]},
            {"$setOnInsert": tag},
            upsert=True
        )
    return list(tag_collection.find({}))


def _classify_scholarship(text: str, threshold: float = 0.50) -> bool:
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
    prompt = (
        "Extract the scholarship award amount from the text. "
        "Return only the dollar amount (e.g. '$5,000'). "
        "If not found, reply 'N/A'.\n\n"
        f"Text: {text[:600]}\n\nAmount:"
    )
    raw = _llm_extract(prompt, max_tokens=15)
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
        f"Return only the exact value mentioned (e.g., '3.0', 'California', 'Computer Science'). "
        f"If no specific requirement is mentioned, reply 'N/A'.\n\n"
        f"Text: {context[:500]}\n\nValue:"
    )
    raw = _llm_extract(prompt, max_tokens=15).lower().strip()
    if any(x in raw for x in ["n/a", "none", "unknown", "not mentioned", "any"]):
        return "any"  
    return raw



# Auto-create a tag type from a discovered keyword 
def _infer_new_tag_from_text(text: str, existing_names: set) -> dict | None:
    """
    When assign_tags() can't reach MIN_TAGS from existing types, this function
    asks the LLM to name ONE additional relevant tag type not already in use.
    If the LLM returns a valid, non-blacklisted name, we upsert it into MongoDB
    and return the full tag doc so it can be included in the current document.
    """
    prompt = (
        "List one important eligibility criterion category for this scholarship "
        "that is NOT already covered by these categories: "
        f"{', '.join(sorted(existing_names))}.\n"
        "Return only the category name as a single lowercase word (e.g. 'religion', 'sport', 'language'). "
        "If none exists, reply 'N/A'.\n\n"
        f"Scholarship text: {text[:600]}\n\nNew category:"
    )
    raw = _llm_extract(prompt, max_tokens=10).lower().strip()

    # Reject non-useful answers
    if (not raw or raw in ("n/a", "none", "other", "general", "any")
            or raw in BLACKLISTED_TAG_NAMES
            or raw in existing_names
            or len(raw) < 3 or len(raw) > 30):
        return None

    # Sanitise: keep only word chars
    clean_name = re.sub(r"[^a-z0-9_]", "", raw)
    if not clean_name:
        return None

    # Generate a description for the new type
    desc_prompt = (
        f"Write a one-sentence description for a scholarship eligibility tag called '{clean_name}'. "
        "Keep it under 15 words."
    )
    description = _llm_extract(desc_prompt, max_tokens=25)
    if not description or len(description) < 5:
        description = f"{clean_name.capitalize()} requirement or characteristic"

    new_tag = {
        "name":        clean_name,
        "description": description,
        "data_type":   "String",
    }

    # Upsert so concurrent workers don't duplicate
    result = tag_collection.find_one_and_update(
        {"name": clean_name},
        {"$setOnInsert": new_tag},
        upsert=True,
        return_document=True,  # pymongo: ReturnDocument.AFTER equivalent
    )
    # find_one_and_update returns the doc; if it was an insert, _id is freshly set
    if result is None:
        result = tag_collection.find_one({"name": clean_name})

    print(f"[ml] Auto-created tag type: '{clean_name}' — {description}")
    return result


# Assign_tags with MIN_TAGS guarantee + auto-creation 
def assign_tags(title: str, summary: str, full_text: str = "", target_count: int = 6) -> list:
    """
      1 — semantic similarity selects which existing tag TYPES apply.
      2 — LLM extracts the value for each selected type.
      3 — if len(assigned) < MIN_TAGS, auto-create new tag types until
                 we hit the minimum or exhaust 3 creation attempts.

    Any tag type with an LLM-extracted value of 'any' is kept only if its
    similarity score is ≥ 0.50; otherwise skipped (same rule as before).
    """
    context_for_match  = f"{title}\n\n{summary}".strip()
    context_for_values = f"{title}\n\n{full_text[:1500]}".strip() if full_text else context_for_match

    existing_tags = ensure_seed_tags()

    if not existing_tags:
        print("[ml] WARNING: tag collection empty even after seeding, force-inserting")
        tag_collection.insert_many([{**tag, "_id": ObjectId()} for tag in SEED_TAGS])
        existing_tags = list(tag_collection.find({}))

    tag_vectors = embedder.encode([t["description"] for t in existing_tags])
    summary_vec = embedder.encode(context_for_match)
    scores = util.cos_sim(summary_vec, tag_vectors)[0]

    score_list = [(existing_tags[i], float(scores[i])) for i in range(len(existing_tags))]
    score_list.sort(key=lambda x: x[1], reverse=True)

    print(f"[ml] All tag scores for '{title[:50]}':")
    for t, s in score_list:
        print(f"      {t['name']}: {round(s, 4)}")

    # Phase 1 + 2: pick top candidates, extract values
    candidates = [
        (t, s) for t, s in score_list
        if t.get("name") not in BLACKLISTED_TAG_NAMES
    ][:target_count]

    assigned       = []
    used_type_ids  = set()
    used_names     = {t["name"] for t in existing_tags}  # for auto-creation dedup

    for tag, score in candidates:
        tag_id = tag["_id"]
        if tag_id in used_type_ids:
            continue

        value = extract_tag_value(context_for_values, tag["name"])
        print(f"[ml] extract_tag_value('{tag['name']}') → {value!r}")

        if value == "any":
            print(f"[ml] Skipping '{tag['name']}' — no specific value found")
            continue

        assigned.append({"tag_type": tag_id, "tag_value": value})
        used_type_ids.add(tag_id)

    # Phase 3: pad to MIN_TAGS by auto-creating new tag types
    attempts = 0
    while len(assigned) < MIN_TAGS and attempts < 3:
        attempts += 1
        current_names = {t["name"] for t in existing_tags} | {
            # include names of tags already assigned (covers auto-created ones)
            tag_collection.find_one({"_id": a["tag_type"]})["name"]
            for a in assigned
        }
        new_tag_doc = _infer_new_tag_from_text(full_text, current_names)
        if new_tag_doc is None:
            print(f"[ml] Could not auto-create tag (attempt {attempts}), stopping early")
            break

        # Extract a value for the new tag
        value = extract_tag_value(context_for_values, new_tag_doc["name"])
    
        # NEW: Skip if value is "any"
        if value == "any":
            print(f"[ml] Skipping auto-created tag '{new_tag_doc['name']}' — no specific value")
            return None

        assigned.append({"tag_type": new_tag_doc["_id"], "tag_value": value})

    print(f"[ml] Final: {len(assigned)} tags assigned to '{title[:50]}'")
    return assigned


# Build a clean description excerpt 
def build_description(text: str, max_chars: int = 800) -> str:
    """
    The schema has a `description` field separate from `summary`.
    We use the first `max_chars` characters of clean body text.
    This gives the front end something to display in a detail view
    without blowing up document size.
    """
    # Strip excess whitespace, collapse runs of blank lines
    cleaned = re.sub(r"\n{3,}", "\n\n", text.strip())
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    if len(cleaned) <= max_chars:
        return cleaned
    # Trim to nearest sentence boundary within max_chars
    truncated = cleaned[:max_chars]
    last_period = truncated.rfind(".")
    if last_period > max_chars * 0.6:
        return truncated[:last_period + 1]
    return truncated + "…"


#  Main pipeline entry point 
def process_raw_document(doc: dict) -> dict | None:
    text  = doc.get("text", "")
    title = doc.get("title", "")

    # ── Step 1: classify ──────────────────────────────────────────────────────
    if not _classify_scholarship(text):
        return None

    # ── Step 2: extract all fields ────────────────────────────────────────────
    name        = extract_name(title, text)
    provider    = extract_provider(text)
    summary     = generate_summary(text)
    description = build_description(text)
    amount      = extract_amount(text)
    essay       = detect_essay_required(text)
    extra_dates = extract_dates(text)
    tags        = assign_tags(
        title=name,
        summary=summary,
        full_text=text,
        target_count=8,   # shoot for 8 so we have slack; MIN_TAGS=4 is the floor
    )

    print(
        f"[ml] name={name!r}  provider={provider!r}  "
        f"essay={essay}  amount={amount!r}  "
        f"tags={len(tags)}  due={extra_dates.get('due')}  "
        f"url={doc['url'][:60]}"
    )

    # ── Step 3: build the cleaned document ───────────────────────────────────
    date_dict = {
        "found": doc.get("scraped_at"),
    }
    
    # Add due date if found
    if "due" in extra_dates:
        date_dict["due"] = extra_dates["due"]
    
    # Add created date if found  
    if "created" in extra_dates:
        date_dict["created"] = extra_dates["created"]

    cleaned = {
        "url":         doc["url"],
        "name":        name,
        "provider":    provider,
        "summary":     summary,
        "description": description,
        "amount":      amount,
        "tags":        tags,
        "date":        date_dict,  # Use the properly constructed dict
        "raw_id": doc["_id"],
    }

    # essay_required is a Boolean in the schema — only set it if we know
    if essay is not None:
        cleaned["essay_required"] = essay

    # ── Step 4: upsert into MongoDB ───────────────────────────────────────────
    clean_collection.update_one(
        {"url": doc["url"]},
        {
            "$set":         cleaned,
            "$setOnInsert": {"id": str(uuid.uuid4())},
        },
        upsert=True,
    )
    return cleaned