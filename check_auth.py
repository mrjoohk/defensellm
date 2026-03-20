import sqlite3
import json

def check_db():
    conn = sqlite3.connect('data/defense.db')
    c = conn.cursor()
    c.execute("SELECT * FROM documents WHERE doc_id LIKE '%STANAG%'")
    print("DB STANAG docs:", c.fetchall())

def check_index():
    with open('data/index/meta.json') as f:
        meta = json.load(f)
        print("Index meta version:", meta.get("index_version"))
    
    # We can also load the index and search it manually
    import sys
    sys.path.append('src')
    from defense_llm.rag.indexer import DocumentIndex
    from defense_llm.rag.embedder import HuggingFaceEmbedder
    
    try:
        import os
        embedder = HuggingFaceEmbedder("sentence-transformers/all-MiniLM-L6-v2")
        index = DocumentIndex(embedder=embedder)
        
        # we might just try reading the index chunks directly
    except Exception as e:
        print("Failed to load embedder", e)

if __name__ == "__main__":
    check_db()
