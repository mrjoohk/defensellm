import requests
import sqlite3

def run(query):
    payload = {
        "question": query,
        "user": {"role": "analyst", "clearance": "PUBLIC", "user_id": "cli-tester"},
        "field_filters": [],
        "top_k": 3,
        "show_citations": True,
        "online_mode": True
    }
    print("Query:", query)
    resp = requests.post("http://localhost:8000/api/query", json=payload)
    print("Answer:", resp.json().get("data", {}).get("answer"))

    conn = sqlite3.connect('data/defense.db')
    c = conn.cursor()
    c.execute("SELECT doc_id, field FROM documents")
    docs = c.fetchall()
    for d in docs:
        if d[0].startswith("WEB"):
            print("WEB DOC FOUND:", d)

if __name__ == "__main__":
    run("Who is the CEO of Lockheed Martin?")
