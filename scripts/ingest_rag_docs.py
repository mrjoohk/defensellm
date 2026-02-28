#!/home/rtv-24n10/anaconda3/envs/defensellm/bin/python
# scripts/ingest_rag_docs.py
import json
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)
REGISTRY = os.path.join(SCRIPT_DIR, "doc_registry.json")
DATA_DIR = os.path.join(BASE_DIR, "data", "rag_docs")

def main():
    if not os.path.exists(REGISTRY):
        print(f"Registry not found: {REGISTRY}")
        sys.exit(1)

    with open(REGISTRY, 'r') as f:
        docs = json.load(f)

    for doc in docs:
        field = doc['field']
        filename = doc['filename']
        pdf_path = os.path.join(DATA_DIR, field, filename)
        
        if not os.path.exists(pdf_path):
            print(f"Skipping {doc['doc_id']}: File {pdf_path} not found (download may have failed).")
            continue

        txt_path = pdf_path.rsplit('.', 1)[0] + '.txt'
        
        # 1) pdf to txt
        print(f"\n--- Processing {doc['doc_id']} ({doc['title']}) ---")
        if not os.path.exists(txt_path):
            res = subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, "pdf_to_txt.py"), pdf_path])
            if res.returncode != 0:
                print(f"Failed to convert PDF for {doc['doc_id']}, skipping ingestion.")
                continue

        # Check if text was extracted successfully and not empty
        if not os.path.exists(txt_path) or os.path.getsize(txt_path) == 0:
            print(f"Skipping {doc['doc_id']}: Empty or missing TXT file.")
            continue

        # 2) ingest utilizing the CLI
        cmd = [
            sys.executable, "-m", "defense_llm.cli", "index",
            txt_path,
            "--doc-id", doc['doc_id'],
            "--doc-rev", doc['doc_rev'],
            "--title", doc['title'],
            "--field", field,
            "--security-label", doc['security_label']
        ]

        # Add optional Playbook metadata
        if 'doc_type' in doc:
            cmd.extend(["--doc-type", doc['doc_type']])
        if 'system' in doc:
            cmd.extend(["--system", doc['system']])
        if 'subsystem' in doc:
            cmd.extend(["--subsystem", doc['subsystem']])
        if 'date' in doc:
            cmd.extend(["--date", doc['date']])
        if 'language' in doc:
            cmd.extend(["--language", doc['language']])
        if 'url' in doc:
            cmd.extend(["--source-uri", doc['url']])
        
        print("Running: " + " ".join(cmd))
        
        # We need to run it from BASE_DIR to make sure python -m defense_llm.cli works
        res = subprocess.run(cmd, cwd=BASE_DIR)
        
        if res.returncode == 0:
            print(f"Successfully ingested {doc['doc_id']}.")
        else:
            print(f"Failed to ingest {doc['doc_id']}. Return code: {res.returncode}")

if __name__ == "__main__":
    main()
