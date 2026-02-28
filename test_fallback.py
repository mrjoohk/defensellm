import requests

payload = {
    "question": "What is HIMARS? Explain its capabilities.",
    "user": {"role": "analyst", "clearance": "PUBLIC", "user_id": "cli-tester"},
    "field_filters": ["ground"],
    "top_k": 3,
    "show_citations": True,
    "online_mode": True
}

resp = requests.post("http://localhost:8000/api/query", json=payload)
print(resp.json())
