import requests

payload = {
    "question": "What is STANAG4586?",
    "user": {"role": "analyst", "clearance": "PUBLIC", "user_id": "cli-tester"},
    "field_filters": [],
    "top_k": 3,
    "show_citations": True,
    "online_mode": False
}
resp = requests.post("http://localhost:8000/api/query", json=payload)
data = resp.json()
print("Answer:", data.get("data", {}).get("answer"))
print("Citations size:", len(data.get("citations", [])))
print("Citations docs:", [c.get("doc_id") for c in data.get("citations", [])])
