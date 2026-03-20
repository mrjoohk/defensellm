import sqlite3

conn = sqlite3.connect('data/defense.db')
c = conn.cursor()
c.execute("SELECT doc_id, field FROM documents")
docs = c.fetchall()
print("All docs:")
for d in docs:
    print(d)
