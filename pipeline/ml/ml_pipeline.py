from transformers import pipeline
from sentence_transformers import SentenceTransformer, util
from pymongo import MongoClient

# 1. Load ML models once (fast)
# Scholarship verification (zero-shot classifier)
classifier = pipeline(
    "zero-shot-classification",
    model="facebook/bart-large-mnli"
)

# Summarization
summarizer = pipeline(
    "summarization",
    model="sshleifer/distilbart-cnn-12-6"
)

# Embeddings for tag matching
embedder = SentenceTransformer("all-MiniLM-L6-v2")

# Tag creation (generative)
generator = pipeline(
    "text2text-generation",
    model="google/flan-t5-small"
)


# 2. MongoDB setup
client = MongoClient("mongodb://mongo:27017")
db = client["scholarship_crawler"]

raw_collection = db["raw_results"]
clean_collection = db["cleaned_scholarships"]
tag_collection = db["tags"]


# 3. Scholarship verification
def verify_scholarship(text: str) -> bool:
    labels = ["scholarship", "not scholarship"]
    result = classifier(text, labels)

    # result["labels"][0] is the highest scoring label
    top_label = result["labels"][0]
    score = result["scores"][0]

    # Require high confidence
    return top_label == "scholarship" and score >= 0.75

# 4. Summarization
def generate_summary(text: str) -> str:
    result = summarizer(text, max_length=120, min_length=40)[0]["summary_text"]
    return result


# 5. Tag matching
def match_tag(summary: str):
    tags = list(tag_collection.find({}))

    if not tags:
        return None, 0.0

    tag_descriptions = [t["description"] for t in tags]
    tag_vectors = embedder.encode(tag_descriptions)
    summary_vec = embedder.encode(summary)

    scores = util.cos_sim(summary_vec, tag_vectors)[0]
    best_idx = scores.argmax().item()
    best_score = scores[best_idx]

    return tags[best_idx], float(best_score)


# 6. New tag creation
def create_new_tag(summary: str):
    prompt = f"Create a short tag name and description for this scholarship:\n\n{summary}"
    result = generator(prompt)[0]["generated_text"]

    # Simple parsing
    parts = result.split("\n")
    name = parts[0].strip()
    description = " ".join(parts[1:]).strip()

    tag_doc = {
        "name": name,
        "description": description
    }

    tag_collection.insert_one(tag_doc)
    return tag_doc


# 7. Full pipeline for one raw document
def process_raw_document(doc):
    text = doc["text"]

    # Step 1: Verify scholarship
    if not verify_scholarship(text):
        print(f"Skipping non-scholarship page: {doc['url']}")
        return None

    # Step 2: Summarize
    summary = generate_summary(text)

    # Step 3: Tag matching
    best_tag, score = match_tag(summary)

    if best_tag and score >= 0.55:
        tag = best_tag
    else:
        tag = create_new_tag(summary)

    # Step 4: Build cleaned scholarship
    cleaned = {
        "url": doc["url"],
        "title": doc["title"],
        "summary": summary,
        "tag": tag,
        "raw_id": doc["_id"]
    }

    clean_collection.insert_one(cleaned)
    return cleaned


# 8. Batch processing
def process_all_raw():
    for doc in raw_collection.find({}):
        process_raw_document(doc)