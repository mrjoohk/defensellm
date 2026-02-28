import json
import yaml
import re
import os

PLAYBOOK_PATH = "docs/Defense_RAG_Improvement_Playbook.md"
DOC_TYPES = ["glossary", "architecture", "interface", "procedure", "test", "spec"]
FIELDS = ["air", "weapon", "ground", "sensor", "comm"]

# Parse FAQs from Playbook
faqs = {f: [] for f in FIELDS}
with open(PLAYBOOK_PATH, "r") as f:
    text = f.read()

for field in FIELDS:
    pattern = rf"## 1\.\d {field.upper()} — 30 FAQs(.*?)## 1\."
    if field == "comm":
        pattern = rf"## 1\.\d {field.upper()} — 30 FAQs(.*?)---"
    
    match = re.search(pattern, text, re.DOTALL)
    if match:
        block = match.group(1)
        # Extract lines like: 1. How do altitude...
        for line in block.split("\n"):
            qm = re.match(r"^\d+\.\s+(.*)", line.strip())
            if qm:
                faqs[field].append(qm.group(1))

# Generate Document Registry (20 per field)
docs = []
coverage_map = []

for field in FIELDS:
    field_docs = []
    doc_idx = 1
    # Distribute the 20 docs among the 6 types (approx 3-4 each)
    type_counts = {"glossary": 3, "architecture": 4, "interface": 3, "procedure": 4, "test": 3, "spec": 3}
    
    for dtype, count in type_counts.items():
        for _ in range(count):
            doc_id = f"DOC-{field.upper()}-{dtype[:3].upper()}-{doc_idx:03d}"
            docs.append({
                "doc_id": doc_id,
                "doc_rev": "v1.0",
                "title": f"Standard {dtype.title()} for {field.title()} Systems Part {doc_idx}",
                "field": field,
                "security_label": "PUBLIC",
                "url": f"https://defense.example.com/{field}/{dtype}_{doc_idx}.pdf",
                "filename": f"{field}_{dtype}_{doc_idx}.txt",
                "doc_type": dtype,
                "system": f"general_{field}",
                "date": "2024-01-01"
            })
            field_docs.append(doc_id)
            doc_idx += 1
            
    # Map FAQs for this field
    for idx, question in enumerate(faqs[field]):
        faq_id = f"{field.upper()}-{idx+1:03d}"
        
        # Pick 2-3 documents that cover this FAQ
        # Just mathematically tie them to ensure diversity
        d1 = field_docs[idx % len(field_docs)]
        d2 = field_docs[(idx + 5) % len(field_docs)]
        
        coverage_map.append({
            "faq_id": faq_id,
            "question": question,
            "must_have_docs": [d1, d2]
        })

# Write the new registry
with open("scripts/doc_registry_v2.json", "w") as f:
    json.dump(docs, f, indent=2)

# Write the coverage map
# Custom yaml dump to make it readable
with open("coverage_map.yaml", "w") as f:
    yaml.dump(coverage_map, f, sort_keys=False, default_flow_style=False)

print(f"Generated {len(docs)} documents.")
print(f"Mapped {len(coverage_map)} FAQs.")
