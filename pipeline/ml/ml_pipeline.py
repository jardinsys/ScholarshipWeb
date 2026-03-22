from transformers import pipeline
from sentence_transformers import SentenceTransformer, util
from pymongo import MongoClient
from bson import ObjectId

# Load ML models 
# Scholarship verification (zero-shot classifier)
classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")

# Summarization
summarizer = pipeline("summarization", model="sshleifer/distilbart-cnn-12-6")

# Embeddings for tag matching
embedder = SentenceTransformer("all-MiniLM-L6-v2")

# Tag creation (generative)
generator = pipeline("text2text-generation", model="google/flan-t5-small")


# MongoDB setup 
client = MongoClient("mongodb://mongo:27017")
db = client["scholarshipdb"]  # shared DB with frontend

raw_collection = db["raw_results"]
clean_collection = db["scholarships"] 
tag_collection = db["tags"]


# Scholarship verification 
def verify_scholarship(text: str) -> bool:
    if not text or len(text.strip()) < 50:
        return False

    labels = ["scholarship", "not scholarship"]
    result = classifier(text, labels)

    top_label = result["labels"][0]
    score = result["scores"][0]

    return top_label == "scholarship" and score >= 0.82


# Summarization
def generate_summary(text: str) -> str:
    result = summarizer(
        text,
        max_length=120,
        min_length=40,
        truncation=True
    )[0]["summary_text"]
    return result


# Extract tag value from text  
def extract_tag_value(summary: str, tag_name: str) -> str:
    # Given an existing tag type name (e.g. "race"), extract the specific value from the scholarship summary (e.g. "black", "hispanic").
    prompt = (
        f"This scholarship summary describes eligible students.\n\n"
        f"Summary: {summary}\n\n"
        f"What is the specific value for the attribute '{tag_name}'? "
        f"Reply with only 1-3 words, nothing else."
    )
    result = generator(prompt, max_new_tokens=10)[0]["generated_text"]
    return result.strip().lower()
 
 
# Create new tag type and extract value 
def create_tag_with_value(summary: str) -> dict:
    # When no existing tag type matches, create a new tag type AND extract its value.
    # Returns {"tag_type": tag_doc, "tag_value": str}
    prompt = (
        "Based on this scholarship summary, identify one eligibility attribute.\n\n"
        f"Summary: {summary}\n\n"
        "Respond in this exact format:\n"
        "TYPE: <1-2 word attribute name, e.g. 'race', 'major', 'state', 'gpa'>\n"
        "VALUE: <specific value from the summary, e.g. 'black', 'engineering', 'ohio'>\n"
        "DESC: <one sentence explaining what this attribute means for matching>"
    )
    result = generator(prompt, max_new_tokens=80)[0]["generated_text"]
 
    # Parse with fallbacks
    tag_name = "general"
    tag_value = "any"
    tag_desc = summary[:100]
 
    for line in result.split("\n"):
        if line.startswith("TYPE:"):
            tag_name = line.replace("TYPE:", "").strip().lower()
        elif line.startswith("VALUE:"):
            tag_value = line.replace("VALUE:", "").strip().lower()
        elif line.startswith("DESC:"):
            tag_desc = line.replace("DESC:", "").strip()
 
    # Reuse existing tag type if name matches
    existing = tag_collection.find_one({"name": tag_name})
    if existing:
        return {"tag_type": existing, "tag_value": tag_value}
 
    tag_doc = {
        "_id": ObjectId(),
        "name": tag_name,
        "description": tag_desc,
        "data_type": "String"
    }
    tag_collection.insert_one(tag_doc)
    return {"tag_type": tag_doc, "tag_value": tag_value}
 
 
# Multi-tag assignment 
def assign_tags(summary: str, target_count: int = 4) -> list:
    # Assign tags to a scholarship.
    ## - If an existing tag type matches → reuse it, extract the value
    ## - If no match → create new tag type and extract value
    # Returns a list of {"tag_type": ObjectId, "tag_value": str}
    
    existing_tags = list(tag_collection.find({}))
    assigned = []
    used_type_ids = set()
 
    # Try to match existing tag types
    if existing_tags:
        tag_descriptions = [t["description"] for t in existing_tags]
        tag_vectors = embedder.encode(tag_descriptions)
        summary_vec = embedder.encode(summary)
        scores = util.cos_sim(summary_vec, tag_vectors)[0]
 
        # Collect matches above threshold sorted by score
        matches = sorted(
            [(existing_tags[i], float(scores[i])) for i in range(len(existing_tags))
             if float(scores[i]) >= 0.50],
            key=lambda x: x[1],
            reverse=True
        )
 
        for tag, score in matches[:target_count]:
            if tag["_id"] not in used_type_ids:
                value = extract_tag_value(summary, tag["name"])
                assigned.append({"tag_type": tag["_id"], "tag_value": value})
                used_type_ids.add(tag["_id"])
 
    # Create new tags to reach target count
    attempts = 0
    while len(assigned) < target_count and attempts < target_count:
        result = create_tag_with_value(summary)
        type_id = result["tag_type"]["_id"]
        if type_id not in used_type_ids:
            assigned.append({"tag_type": type_id, "tag_value": result["tag_value"]})
            used_type_ids.add(type_id)
        attempts += 1
 
    return assigned
 
 
# Full pipeline for one raw document
def process_raw_document(doc):
    text = doc["text"]
 
    # Step 1: Verify scholarship
    if not verify_scholarship(text):
        print(f"Skipping non-scholarship page: {doc['url']}")
        return None
 
    # Step 2: Summarize
    summary = generate_summary(text)
 
    # Step 3: Assign tags (reuse existing types + extract values, create new if needed)
    tags = assign_tags(summary, target_count=4)
 
    # Step 4: Build cleaned scholarship document
    cleaned = {
        "url": doc["url"],
        "name": doc["title"],
        "summary": summary,
        "tags": tags,  # list of {tag_type: ObjectId, tag_value: str}
        "date": {
            "found": doc.get("scraped_at")
        },
        "raw_id": doc["_id"]
    }
 
    # Avoid duplicate URLs
    clean_collection.update_one(
        {"url": doc["url"]},
        {"$set": cleaned},
        upsert=True
    )
 
    return cleaned
 
 
# Batch processing
def process_all_raw():
    for doc in raw_collection.find({}):
        process_raw_document(doc)