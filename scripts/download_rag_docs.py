import json
import os
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(BASE_DIR, "data", "rag_docs")
REGISTRY = os.path.join(SCRIPT_DIR, "doc_registry.json")

print(f"Reading registry: {REGISTRY}")

with open(REGISTRY, 'r') as f:
    docs = json.load(f)

for doc in docs:
    field = doc['field']
    url = doc['url']
    filename = doc['filename']
    out_dir = os.path.join(DATA_DIR, field)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, filename)

    if os.path.exists(out_path):
        print(f"Already downloaded: {out_path}")
        continue

    print(f"Downloading {filename} for domain {field}...")
    
    if filename.endswith(".txt") and "wikipedia.org" in url:
        page_title = url.split('/')[-1]
        api_url = f"https://en.wikipedia.org/w/api.php?format=json&action=query&prop=extracts&explaintext=1&titles={page_title}"
        res = subprocess.run(["curl", "-s", "-L", api_url], capture_output=True, text=True)
        if res.returncode == 0:
            try:
                data = json.loads(res.stdout)
                pages = data.get("query", {}).get("pages", {})
                for page_id, page_data in pages.items():
                    extract = page_data.get("extract", "")
                    if extract:
                        with open(out_path, "w", encoding="utf-8") as tf:
                            tf.write(extract)
                        print(f"Download success: {out_path}")
            except Exception as e:
                print(f"Failed to parse Wikipedia JSON: {e}")
        continue
    
    # PDF curl download
    res = subprocess.run(['curl', '-L', '-f', '-s', '-A', 'Mozilla/5.0', '-o', out_path, url])
    
    if res.returncode == 0:
        if os.path.exists(out_path) and os.path.getsize(out_path) < 10000:
            print(f"Downloaded file {out_path} is suspiciously small, likely a blocked page. Removing.")
            os.remove(out_path)
        else:
            print(f"Download success: {out_path}")
    else:
        print(f"Download failed for {url}")
        if os.path.exists(out_path):
            os.remove(out_path)

print("Download process completed.")
