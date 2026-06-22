import pymongo
import time
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError

client = pymongo.MongoClient("mongodb://mongodb:27017/")
db = client["auto_collection_data_marketing"]

domains = ["avakids.com", "aeoneshop.com", "thegioisua.com", "concung.com", "bachhoaxanh.com"]

# 1. Clear mock data
db.sources.delete_many({"source_id": {"$in": domains}})
db.sc_products.delete_many({"domain": {"$in": domains}})
db.sc_raw_pages.delete_many({"domain": {"$in": domains}})
db.sc_offers.delete_many({"domain": {"$in": domains}})

print("Mock data cleared.")

# 2. Add real source
source_id = "real_thegioisua"
db.sources.update_one(
    {"source_id": source_id},
    {"$set": {
        "source_id": source_id,
        "name": "Thế Giới Sữa",
        "domain": "thegioisua.com",
        "url": "https://thegioisua.com/sua-tuoi",
        "category": "Sữa",
        "status": "Hoạt động",
        "type": "E-commerce"
    }},
    upsert=True
)

def http_json(method: str, url: str, payload=None):
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Accept": "application/json"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    req = Request(url, data=data, headers=headers, method=method.upper())
    with urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))

print("Triggering collection...")
resp = http_json("POST", f"http://localhost:8080/api/sources/{source_id}/collect")
print("Collect Response:", resp)

print("Waiting for raw artifacts...")
found_artifacts = []
for _ in range(30):
    time.sleep(2)
    try:
        data = http_json("GET", f"http://localhost:8080/api/sources/{source_id}/discovery")
        if data.get("raw_artifacts"):
            found_artifacts = data["raw_artifacts"]
            print(f"Found {len(found_artifacts)} raw artifacts!")
            break
    except HTTPError:
        pass
else:
    print("No raw artifacts found after 60s")
    exit(1)

print("Running Gemini AI analysis...")
for artifact in found_artifacts:
    payload = {
        "domain": "thegioisua.com",
        "raw_artifact_id": artifact["id"],
        "target_hint": "product_listing"
    }
    resp = http_json("POST", "http://localhost:8080/api/extraction/ai/analyze", payload)
    print("AI Analyze Response:", resp)

