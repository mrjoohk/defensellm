import requests

payload = {
    "question": "제2차 세계 대전 중 전투기의 주요 역할은 무엇입니까?",
    "user": {"role": "analyst", "clearance": "PUBLIC", "user_id": "cli-tester"},
    "field_filters": ["air"],
    "top_k": 3,
    "show_citations": True
}

resp = requests.post("http://localhost:8000/api/query", json=payload)
data = resp.json()
print("Answer:", data.get("data", {}).get("answer"))
print("Citations size:", len(data.get("citations", [])))
