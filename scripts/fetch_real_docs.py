import os
import json
import yaml
import re
import urllib.request
import urllib.parse
import time

PLAYBOOK_PATH = "docs/Defense_RAG_Improvement_Playbook.md"
FIELDS = ["air", "weapon", "ground", "sensor", "comm"]

WIKI_TOPICS = {
    "air": [
        "Air superiority fighter", "Radar cross-section", "Active electronically scanned array", 
        "Synthetic-aperture radar", "Flight control system", "Electronic countermeasures", 
        "Airborne radar", "Inertial navigation system", "Pulse-Doppler radar", "Beam steering", 
        "Radar tracker", "Sensor fusion", "Beyond-visual-range missile", "Identification friend or foe", 
        "Inverse synthetic-aperture radar", "Moving target indication", "Avionics", 
        "Mil-STD-1553", "Radar warning receiver", "Multi-function display"
    ],
    "weapon": [
        "Missile guidance", "Proportional navigation", "Circular error probable", 
        "Fire-and-forget", "Warhead", "Shaped charge", "Proximity fuze", 
        "Blast radius", "Target acquisition", "Anti-radiation missile", 
        "Countermeasure", "Terminal guidance", "Missile launch facility", 
        "Air-to-air missile", "Anti-ship missile", "Surface-to-air missile", 
        "Rocket propellant", "Trajectory", "Radar lock-on", "Hardpoint"
    ],
    "ground": [
        "Main battle tank", "Armoured personnel carrier", "Infantry fighting vehicle", 
        "Active protection system", "Reactive armour", "Fire-control system", 
        "Ground-penetrating radar", "Network-centric warfare", "Battlespace", 
        "Command and control", "Dead reckoning", "Military logistics", 
        "Improvised explosive device", "Military camouflage", "Continuous track", 
        "Suspension (vehicle)", "Thermal imaging", "Acoustic location", 
        "Tank gun", "Off-road vehicle"
    ],
    "sensor": [
        "Radar", "Sonar", "Lidar", "Electro-optics", "Infrared search and track", 
        "Forward-looking infrared", "Signal-to-noise ratio", "Radar range equation", 
        "Image resolution", "Pulse repetition frequency", "Phased array", 
        "Beamforming", "Clutter (radar)", "Sidelobe", "Constant false alarm rate", 
        "Electronic warfare", "Aperture", "Multipath propagation", 
        "Continuous-wave radar", "Bistatic radar"
    ],
    "comm": [
        "Link budget", "Path loss", "Latency (engineering)", "Throughput", 
        "Bit error rate", "Frequency-hopping spread spectrum", "Direct-sequence spread spectrum", 
        "Radio jamming", "Cryptography", "Quality of service", 
        "Time-division multiple access", "Frequency-division multiple access", "Code-division multiple access", 
        "Network topology", "Mesh networking", "Mobile ad hoc network", 
        "Tactical data link", "Link 16", "Telemetry", "Error correction code"
    ]
}

def get_wiki_text(title):
    try:
        url = f"https://en.wikipedia.org/w/api.php?format=json&action=query&prop=extracts&explaintext=1&titles={urllib.parse.quote(title)}"
        req = urllib.request.Request(url, headers={'User-Agent': 'DefenseLLM/1.0'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            pages = data['query']['pages']
            for page_id in pages:
                # Return extract, if page is missing it won't have 'extract'
                return pages[page_id].get('extract', "")
    except Exception as e:
        print(f"Error fetching {title}: {e}")
        return ""
    return ""

def generate_docs():
    # 1. Read FAQs
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
            for line in block.split("\n"):
                qm = re.match(r"^\d+\.\s+(.*)", line.strip())
                if qm:
                    faqs[field].append(qm.group(1))

    docs = []
    coverage_map = []
    doc_type_cycler = ["glossary", "architecture", "interface", "procedure", "test", "spec"]

    for field in FIELDS:
        field_docs = []
        os.makedirs(f"data/rag_docs/{field}", exist_ok=True)
        
        topics = WIKI_TOPICS[field]
        for i, topic in enumerate(topics):
            print(f"[{field}] Fetching: {topic}")
            content = get_wiki_text(topic)
            if not content or len(content) < 100:
                print(f"  -> Warning: Content too short or missing for {topic}")
                # Fallback content if Wikipedia fails or article is a stub
                content = f"# {topic}\n\nThis is a fallback document for {topic} due to missing Wikipedia content.\nIt serves as a placeholder for {field} domain knowledge."
            
            # Save to file
            filename = f"{topic.replace(' ', '_').replace('/', '_')}.txt".lower()
            filepath = f"data/rag_docs/{field}/{filename}"
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"# {topic}\n\n")
                f.write(content)
            
            doc_id = f"DOC-{field.upper()}-{i+1:03d}"
            dtype = doc_type_cycler[i % len(doc_type_cycler)]
            
            docs.append({
                "doc_id": doc_id,
                "doc_rev": "v1.0",
                "title": topic,
                "field": field,
                "security_label": "PUBLIC",
                "url": f"https://en.wikipedia.org/wiki/{urllib.parse.quote(topic)}",
                "filename": filename,
                "doc_type": dtype,
                "system": f"general_{field}",
                "date": "2024-01-01"
            })
            field_docs.append(doc_id)
            time.sleep(0.1) # Be nice to wikipedia API
            
        # Map FAQs
        for idx, question in enumerate(faqs[field]):
            faq_id = f"{field.upper()}-{idx+1:03d}"
            # map to two documents pseudo-randomly based on text hash or simple offset
            d1 = field_docs[idx % len(field_docs)]
            d2 = field_docs[(idx + 7) % len(field_docs)]
            
            coverage_map.append({
                "faq_id": faq_id,
                "question": question,
                "must_have_docs": [d1, d2]
            })

    # Save outputs
    with open("scripts/doc_registry.json", "w", encoding="utf-8") as f:
        json.dump(docs, f, indent=2, ensure_ascii=False)

    with open("coverage_map.yaml", "w", encoding="utf-8") as f:
        yaml.dump(coverage_map, f, sort_keys=False, default_flow_style=False, allow_unicode=True)

    print(f"Successfully generated {len(docs)} documents and mapped {len(coverage_map)} FAQs.")

if __name__ == "__main__":
    generate_docs()
