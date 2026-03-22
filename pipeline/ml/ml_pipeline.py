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
generator = pipeline("text2text-generation", model="google/flan-t5-large")


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

    return top_label == "scholarship" and score >= 0.85


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
    prompt = (
        f"What is the specific value for '{tag_name}' in this scholarship? "
        f"Reply with only 1-3 words.\n\n"
        f"Scholarship: {summary[:300]}"
    )
    result = generator(prompt, max_new_tokens=8)[0]["generated_text"].strip().lower()
    result = result.split("\n")[-1].strip()

    if not result or len(result) > 30: return "any"
    return result
 
 
# Create new tag type and extract value 
def create_tag_with_value(summary: str, hint: str ="") -> dict:
    # Ask for type and value in two separate calls — more reliable for small models
    type_prompt = (
        f"{hint}\n\n" if hint else ""
    ) + (
        f"What is one eligibility requirement category for this scholarship? "
        f"Reply with only 1-2 words like 'race', 'major', 'state', 'gpa', 'religion', 'gender'.\n\n"
        f"Scholarship: {summary[:300]}"
    )
    tag_name = generator(type_prompt, max_new_tokens=8)[0]["generated_text"].strip().lower()
    tag_name = tag_name.split("\n")[-1].strip()

    value_prompt = (
        f"What is the specific value for '{tag_name}' in this scholarship? "
        f"Reply with only 1-3 words.\n\n"
        f"Scholarship: {summary[:300]}"
    )
    tag_value = generator(value_prompt, max_new_tokens=8)[0]["generated_text"].strip().lower()
    tag_value = tag_value.split("\n")[-1].strip()

    desc_prompt = (
        f"In one sentence, describe what '{tag_name}' means as a scholarship eligibility filter."
    )
    tag_desc = generator(desc_prompt, max_new_tokens=30)[0]["generated_text"].strip()
    tag_desc = tag_desc.split("\n")[-1].strip()

    if not tag_name or len(tag_name) > 20:
        tag_name = "eligibility"
    if not tag_value or len(tag_value) > 30:
        tag_value = "see description"
    if not tag_desc:
        tag_desc = f"Eligibility requirement: {tag_name}"

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
def assign_tags(summary: str, target_count: int = 5) -> list:
    # Assign tags to a scholarship.
    ## - If an existing tag type matches → reuse it, extract the value
    ## - If no match → create new tag type and extract value
    # Returns a list of {"tag_type": ObjectId, "tag_value": str}
    
    existing_tags = list(tag_collection.find({}))
    assigned = []
    used_type_ids = set()

    # Step 1: Match existing tag types
    if existing_tags:
        tag_descriptions = [t["description"] for t in existing_tags]
        tag_vectors = embedder.encode(tag_descriptions)
        summary_vec = embedder.encode(summary)
        scores = util.cos_sim(summary_vec, tag_vectors)[0]

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

    # Step 2: Keep creating new tags until we hit target_count
    # Use different prompt angles to get variety
    angles = [
        "Who is eligible based on race, ethnicity, or background?",
        "What field of study or major is required?",
        "What state, region, or location is required?",
        "What GPA, grade level, or academic requirement is needed?",
        "What other eligibility requirement exists (gender, religion, disability, income)?",
        "What career or industry is this scholarship for?",
    ]

    angle_index = 0
    max_attempts = target_count * 3  # allow extra attempts to avoid infinite loop
    attempts = 0

    while len(assigned) < target_count and attempts < max_attempts:
        # Pick a different angle each attempt to get variety
        angle = angles[angle_index % len(angles)]
        angle_index += 1
        attempts += 1

        result = create_tag_with_value(summary, hint=angle)
        type_id = result["tag_type"]["_id"]

        if type_id not in used_type_ids:
            assigned.append({"tag_type": type_id, "tag_value": result["tag_value"]})
            used_type_ids.add(type_id)

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