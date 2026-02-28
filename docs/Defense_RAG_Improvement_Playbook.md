# Defense Domain RAG Improvement Playbook (Qwen2.5 1.5B)
Generated: 2026-02-25 05:32:07 (Asia/Seoul)

This document is a **step-by-step** guide to build and iteratively improve a defense-domain RAG system with **5 fields**:
- `air`, `weapon`, `ground`, `sensor`, `comm`

It includes:
- 30 FAQs per field (150 total)
- A concrete document collection plan (~20 docs/field) with examples
- Chunking + metadata + dedup rules (with examples)
- Evaluation plan (Top‑k recall / rerank / answer accuracy)
- Targeted collection loop (no random additions)
- Evaluation dataset template (question‑answer‑evidence) + examples

> **Note**: Keep everything **public / non-sensitive** and compliant with your org’s policies.

---

## Step 0 — Define your scope & constraints (1-time)
**Goal:** Make the RAG system predictable and measurable.

**Decide:**
- Target users (engineers, operators, analysts)
- Allowed sources (public standards, open research, vendor public whitepapers, etc.)
- Output policy (must cite sources, no guessing, confidence signaling)

**Minimal system constraints (recommended for 1.5B):**
- Always answer with **(a) short answer** + **(b) cited evidence bullets**
- If evidence is missing, reply: “Not enough evidence in retrieved docs” + list what’s missing

---

# Step 1 — Build FAQ-driven “Query Set” (30 per field)

These questions are **not** the final eval set yet. They are your **collection compass** and later become eval prompts.

## 1.1 AIR — 30 FAQs
1. How do altitude and aspect angle affect radar detection range for airborne targets?
2. What parameters most strongly influence aircraft radar cross section (RCS)?
3. What are typical mission computer subsystems (navigation, stores, sensor fusion) and interfaces?
4. How does an AESA radar steer beams (electronic scanning) and what are practical constraints?
5. What is PRF and how is it selected for different airborne radar modes?
6. What are key differences between SAR and ISAR and when is each used?
7. How do platform speed and trajectory affect SAR azimuth resolution?
8. What are common INS/GNSS integration architectures and error sources?
9. How do flight control modes differ (manual, SAS, autopilot, FBW control laws)?
10. What is flight envelope protection and what limits are typically enforced?
11. How does ECM/EA affect track stability and false targets?
12. What are common radar tracking filters (α‑β, Kalman) and tuning considerations?
13. How does antenna aperture size relate to beamwidth and gain?
14. What is Doppler bandwidth and what platform factors control it?
15. How does vibration/attitude jitter degrade EO/IR stabilization and SAR imaging?
16. What is clutter and how is clutter suppression achieved (MTI/MTD, STAP basics)?
17. What are typical airborne databus standards and use cases (1553, Ethernet, ARINC-like concepts)?
18. What is sensor fusion at the aircraft level (track-to-track vs measurement fusion)?
19. How does data link latency influence BVR engagement timelines?
20. What are typical payload power/thermal constraints and how do they impact mission duration?
21. How is radar calibration performed (internal/external calibration concepts)?
22. What is look angle/incidence angle and how does it affect SAR resolution and radiometry?
23. What are common antenna scan patterns and revisit-time trade-offs?
24. How do weather and atmospheric effects influence EO/IR and radar sensing?
25. What are typical radar modes (RWS/TWS/GMTI/SAR) and their output products?
26. How is target classification supported (features, confidence, multi-sensor cues)?
27. What is IFF/Mode integration conceptually and what are typical platform integration concerns?
28. What are weapon-to-aircraft integration requirements (stores management, safe separation basics)?
29. What is the difference between track, plot, and detection in sensor processing pipelines?
30. What are mission data files / threat libraries and how are they updated and validated?

## 1.2 WEAPON — 30 FAQs
1. What is the kill chain and how does it map to weapon employment steps?
2. What is No‑Escape Zone (NEZ) and how is it estimated conceptually?
3. What are common guidance laws (PN/APN) and when are they used?
4. What is LOAL vs LOBL and what system support is required?
5. How do seeker FOV and gimbal limits affect acquisition and terminal performance?
6. What are midcourse guidance and datalink updates, and what messages are typically needed?
7. What is time‑to‑go and why is it important for guidance and fuzing?
8. How do propulsion phases (boost/sustain) affect engagement envelopes?
9. What are typical fuze types and arming/SAFE conditions?
10. What are typical warhead effects (blast/frag/shaped charge) at a conceptual level?
11. What is CEP and what error sources contribute (navigation, guidance, environment)?
12. How is Pk (probability of kill) estimated conceptually and what drives it?
13. How does countermeasure resistance get characterized (conceptual test factors)?
14. What are typical missile/weapon health monitoring signals (BIT concepts)?
15. What defines a weapon’s flight envelope and constraints (speed/altitude/turn rate)?
16. What is lofting and why might it improve range/energy in some scenarios?
17. What are safe separation requirements and why do they differ by store and platform?
18. What coordinate formats are used for targeting (geodetic, ECEF, local ENU) and pitfalls?
19. How is impact angle controlled and why does it matter (top‑attack concepts)?
20. What is terminal guidance handover (inertial→seeker) and failure modes?
21. How are aerodynamic coefficients (Cd, Cl) modeled and validated conceptually?
22. What is seeker cooling and why does it matter for IR seekers?
23. What are typical engagement timeline phases and decision points?
24. How is weapon integration tested (ground test, captive carry, live fire) at high level?
25. What are abort/safe conditions and weapon inhibit logic concepts?
26. What is proximity vs contact fuze trade-off?
27. How does target maneuver influence required guidance performance?
28. What are typical data items in a weapon status message (arming, BIT, temp, battery)?
29. How is weapon simulation validated (truth model vs HWIL/SIL) conceptually?
30. What are common causes of miss distance growth and mitigation concepts?

## 1.3 GROUND — 30 FAQs
1. What defines ground vehicle mobility (power-to-weight, traction, terrain, suspension)?
2. How are protection levels and vulnerability assessed (ballistic/IED concepts)?
3. What are typical ground C2 node functions and data flows?
4. What are common ground sensor types (ground radar, EO/IR mast, acoustic) and roles?
5. How does terrain affect line-of-sight and communications planning?
6. What is a fire-control loop for ground systems (detect→track→engage)?
7. How is stabilization achieved for turreted sensors/weapons (concepts)?
8. What are typical navigation approaches in GPS-denied environments (dead reckoning, map matching)?
9. How is terrain data represented (DEM/DTED concepts) and typical resolution considerations?
10. What are typical battlefield networks (mesh, hub-spoke) and integration considerations?
11. What are common IFF integration concerns on the ground (conceptual)?
12. How does ground clutter affect radar detection and tracking?
13. What is signature management (thermal, acoustic, RF) and key levers?
14. How is maintenance readiness measured (MTBF/MTTR concepts)?
15. What are logistics constraints that impact operational availability?
16. What defines cross-country speed and what terrain factors dominate?
17. How is recoil management handled in vehicle-mounted systems (concepts)?
18. What is autonomous ground navigation at a high level (perception→planning→control)?
19. How does convoy communications reliability degrade and what mitigations exist?
20. What are typical command message types (tasking, status, alerts) for ground units?
21. How is sensor fusion performed at a ground node (track management concepts)?
22. What are typical environmental effects on sensors (dust, smoke, rain, heat haze)?
23. What are common interoperability pain points between ground platforms and higher C2?
24. How are maps and operational overlays structured and updated?
25. What are typical power subsystem constraints for ground platforms (silent watch concepts)?
26. How do rules of engagement constraints affect system design (conceptual)?
27. What are common causes of false alarms and how are they reduced?
28. How is survivability measured (mission kill vs mobility kill concepts)?
29. What are typical databus / vehicle network architectures (CAN/Ethernet concepts)?
30. What standards or profiles are often used for reporting tracks and events (conceptual)?

## 1.4 SENSOR — 30 FAQs
1. What is SNR and how does it relate to detection performance?
2. What is the radar range equation at a conceptual level and key parameters?
3. How do bandwidth and pulse characteristics set range resolution?
4. How does antenna aperture affect beamwidth and gain?
5. What is PRF trade-off (range ambiguity vs Doppler ambiguity)?
6. What is coherent integration time and its constraints?
7. What is Doppler ambiguity and how is it mitigated?
8. What is range gating and why is it used for compute reduction?
9. What are sidelobes and how do windowing/apodization methods reduce them?
10. What is radiometric accuracy and what calibration steps influence it?
11. What is phase noise and how does it degrade coherent processing?
12. What is polarization and when is polarization diversity valuable?
13. What is beamforming (analog/digital) and what are key array constraints?
14. What is clutter modeling (land/sea) at a conceptual level?
15. What is SAR azimuth resolution and what controls it?
16. What are common SAR image artifacts (defocus, layover, shadow) and their causes?
17. What is multi-bounce scattering and why does it matter in urban scenes?
18. What is BRDF and why does it matter for EO reflectance modeling?
19. What is NETD for thermal sensors and how does it relate to detection?
20. What is ADC sampling rate and what constraints drive it?
21. How are detection thresholds set (CFAR concepts) and trade-offs?
22. How is sensor calibration performed and verified (conceptual)?
23. What is interference/jamming and baseline mitigation techniques?
24. What is antenna element spacing rule-of-thumb and grating lobes?
25. How does platform motion error affect SAR focusing and compensation concepts?
26. How is RCS measured (conceptual setups) and how is it used in modeling?
27. What is GMTI and how does it differ from SAR in processing objectives?
28. What is sensor fusion between radar and EO/IR (cueing concepts)?
29. What defines update rate vs resolution trade-offs?
30. What is data quality metadata (uncertainty, confidence) and why it matters?

## 1.5 COMM — 30 FAQs
1. What is a link budget and what terms dominate it?
2. How is path loss estimated (free-space vs additional losses)?
3. What are key drivers of latency (propagation, processing, routing)?
4. What limits throughput (bandwidth, modulation, coding, protocol overhead)?
5. How is modulation/coding selected for robustness vs capacity?
6. What is BER/PER and how do they relate to perceived reliability?
7. What is frequency hopping/spread spectrum at a conceptual level and why used?
8. What are common anti-jam techniques (power control, coding, hopping, routing diversity)?
9. How is encryption integrated (key management concepts) without breaking latency constraints?
10. What is QoS and how does it prioritize C2 messages vs bulk data?
11. How is time synchronization maintained (GNSS time, network time) and why it matters?
12. What are typical network topologies (mesh, star, relay) and trade-offs?
13. How do packet loss and retransmissions affect real-time control loops?
14. What is redundancy (dual links, diverse paths) and how is failover handled?
15. What is secure key exchange conceptually and operational constraints?
16. How is SATCOM latency modeled and what apps tolerate it?
17. What are LOS/NLOS constraints and relay planning concepts?
18. TDMA vs FDMA vs CDMA trade-offs at a conceptual level
19. What is waveform certification/interoperability testing conceptually?
20. What defines network resilience and how is it measured?
21. How is routing optimized under mobility and jamming?
22. What is spectrum efficiency and when does it matter most?
23. How is multicast/broadcast handled reliably?
24. What antenna alignment/stabilization constraints impact comm links?
25. What is link adaptation (rate, power, coding) and triggers?
26. How is bandwidth allocation handled among competing users?
27. What is EMCON and how does it affect comm design?
28. How is data integrity verified (checksums, auth) at a conceptual level?
29. How is cyber resilience assessed for comm nodes (conceptual)?
30. What logging/telemetry is required to diagnose comm issues in the field?

---

# Step 2 — Collect ~20 documents per field (document type diversity)

**Rule:** Do **not** collect “random 20”. Collect **by type** and **by FAQ coverage**.

## 2.1 Per-field target mix (~20)
- **Glossary / Terminology**: 2–3
- **Architecture / CONOPS / Concepts**: 3–4
- **Interface / ICD / Data dictionary**: 3–5
- **Procedures / Ops / Checklists**: 3–4
- **Test / Evaluation / Performance**: 2–3
- **Standards / Specs (public)**: 2–3

Total: **15–22 docs/field** (start at ~20).

## 2.2 Example: COMM field doc plan (sample)
- Glossary: “Tactical datalink terminology”, “QoS terms”
- Architecture: “Network overview”, “Waveform overview”
- Interface: “Message field dictionary”, “Network status telemetry schema”
- Procedures: “Radio configuration SOP”, “Key load procedure (public template)”
- Test: “Link budget test report template”, “Range test checklist”
- Standards: Public comm protocol specs / IEEE-like references where applicable

## 2.3 Coverage mapping (mandatory)
Create `coverage_map.yaml`:
- Each FAQ → list of documents expected to answer it
- Each document → list of FAQs it supports

Example:
```yaml
- faq_id: COMM-01
  question: "What is a link budget and what terms dominate it?"
  must_have_docs:
    - comm_link_budget_guide.pdf
    - comm_waveform_overview.md
```

**Acceptance target:** Each FAQ should map to **≥2 docs** (primary + backup).

---

# Step 3 — Apply chunking + metadata + dedup (with concrete rules)

## 3.1 Metadata schema (recommended minimal)
Attach metadata to **every chunk**:

```json
{
  "field": "sensor",
  "doc_id": "sensor_radar_theory_2024",
  "doc_type": "spec",
  "title": "Radar Theory Basics",
  "system": "airborne_radar",
  "subsystem": "sar_processing",
  "version": "v1.0",
  "date": "2024-06-01",
  "language": "en",
  "security": "public",
  "source_uri": "local://docs/sensor/radar_theory_basics.pdf",
  "section_path": "3.2 SAR > 3.2.5 Azimuth Resolution",
  "page_range": "12-13",
  "chunk_id": "sensor_radar_theory_2024::p12-13::c003"
}
```

**Why it matters:** small models need strong metadata filters to avoid pulling irrelevant chunks.

## 3.2 Chunking rules (heading-aware + structure-preserving)
**Default targets (start-point):**
- 350–900 tokens per chunk
- overlap 10–15% only when needed
- Keep these together:
  - definition + constraints + equation
  - procedure steps + prerequisites
  - interface field + description + units

**Do:**
- Split by headings (H1/H2/H3) first
- Preserve tables as table blocks (row-wise if too big)
- Keep bullet lists intact

**Don’t:**
- Split mid-equation or mid-table
- Create 1–2 sentence microchunks (hurts retrieval)

### Example (good chunk)
**Section:** “3.2.5 Azimuth Resolution”
- Definition paragraph
- Equation/derivation summary
- Parameter explanation (aperture, wavelength)
- 1–2 constraints bullets

### Example (bad chunk)
- 1 paragraph with only “Azimuth resolution is…”
- Next chunk contains only the equation with no explanation

## 3.3 Dedup rules (exact + near-dup)
- Exact duplicate: hash (SHA-256) of normalized text → drop duplicates
- Near-duplicate: embedding cosine similarity > 0.95 within same field/doc_type → keep the newest (by date/version) or the longer/more complete chunk

**Normalization suggestion:**
- Strip repeated headers/footers
- Collapse whitespace
- Remove page numbers only (keep section titles)

---

# Step 4 — Evaluate: Top‑k recall / rerank / answer accuracy

You will evaluate **retrieval** separately from **generation**.

## 4.1 Metrics (minimum set)
**Retrieval:**
- Top‑k Recall (k=3,5,10): does any retrieved chunk contain the labeled evidence?
- MRR: how high the first relevant chunk ranks

**Reranking:**
- Rerank Recall@k
- NDCG@k (optional)

**Answer quality (with citations):**
- Exact/Soft match (or rubric score)
- Grounded citation rate (answer cites the required evidence)
- “Abstain when missing evidence” rate (should be high, not hallucinating)

## 4.2 Evaluation pipeline (reference)
1. Query → Retriever (Top‑k)
2. Reranker → re-order Top‑k
3. Generator (Qwen2.5 1.5B) uses Top‑n (e.g., 3–5) chunks
4. Compare:
   - retrieved chunks vs required evidence
   - answer vs expected answer
   - citations vs required evidence

## 4.3 Recommended thresholds to start (tune later)
- Retrieval Recall@5 ≥ 0.80
- Rerank Recall@5 ≥ 0.88
- Grounded citation rate ≥ 0.75
- Hallucination rate (no-evidence answers) ≤ 0.10

---

# Step 5 — Fill gaps via targeted collection (no random additions)

When a metric fails, you **do not** “add more random docs.”

## 5.1 Gap classification
For each failed question, tag the root cause:
- **R1**: missing document coverage (no doc answers it)
- **R2**: bad chunking (answer exists but split poorly)
- **R3**: missing metadata (filters cannot narrow)
- **R4**: retrieval mismatch (embedding poor)
- **R5**: reranker mismatch
- **G1**: generation prompt/policy problem (model ignores evidence)
- **G2**: answer requires multi-hop reasoning; needs better evidence packaging

## 5.2 Targeted action table (example)
| Cause | Symptom | Fix |
|---|---|---|
| R1 | No chunk contains required evidence | Add 1–3 authoritative docs **of the missing type** |
| R2 | Evidence exists but never retrieved | Re-chunk affected sections (keep definition+equation) |
| R3 | Wrong-field chunks retrieved | Add `system/subsystem/section_path` metadata + filters |
| R4 | Similar terms collide | Add query rewrite + synonyms dictionary |
| R5 | Relevant chunk ranked low | Train/replace reranker or add hard negatives |
| G1 | Hallucinated answer with evidence present | Enforce “cite or abstain” prompt |
| G2 | Needs multi-hop | Add “summary chunks” or “concept sheets” per topic |

---

# Step 6 — Evaluation dataset template (Q-A-Evidence) + examples

Create a repo folder:
```
eval/
  queries.yaml
  rubrics.yaml
  results/
```

## 6.1 YAML template (recommended)
```yaml
- id: SENSOR-001
  field: sensor
  question: "How do bandwidth and pulse characteristics set range resolution?"
  expected_answer:
    short: "Range resolution is primarily determined by signal bandwidth; larger bandwidth yields finer range resolution."
    must_include:
      - "bandwidth"
      - "range resolution"
  required_evidence:
    - doc_id: sensor_radar_theory_2024
      section_path_contains: "Range Resolution"
  negative_evidence:  # optional
    - doc_id: sensor_random_appendix_2019
  difficulty: easy
  tags: ["radar", "range_resolution"]
```

## 6.2 Answer scoring rubric (minimal)
- 2 points: Correct short answer + includes must_include terms
- 1 point: Partially correct or missing one must_include
- 0 points: Incorrect / not grounded / no evidence

## 6.3 Example entries (5 samples)
```yaml
- id: COMM-001
  field: comm
  question: "What is a link budget and what terms dominate it?"
  expected_answer:
    short: "A link budget accounts for transmitted power, gains, losses, and noise to predict received SNR and margin."
    must_include: ["power", "gain", "loss", "noise", "SNR"]
  required_evidence:
    - doc_id: comm_link_budget_guide_2025
      section_path_contains: "Link Budget"
  difficulty: easy
  tags: ["link_budget"]

- id: AIR-004
  field: air
  question: "How does platform speed affect SAR azimuth resolution?"
  expected_answer:
    short: "Speed affects Doppler history and aperture time; azimuth resolution depends on effective aperture and wavelength rather than speed alone, but speed changes sampling/revisit constraints."
    must_include: ["azimuth resolution", "aperture", "Doppler"]
  required_evidence:
    - doc_id: air_sar_processing_note_2024
      section_path_contains: "Azimuth Resolution"
  difficulty: medium
  tags: ["sar", "azimuth"]

- id: WEAPON-003
  field: weapon
  question: "What are common guidance laws (PN/APN) and when are they used?"
  expected_answer:
    short: "PN commands acceleration proportional to line-of-sight rate; APN augments PN for target acceleration, improving performance against maneuvering targets."
    must_include: ["line-of-sight", "PN", "APN"]
  required_evidence:
    - doc_id: weapon_guidance_overview_2023
      section_path_contains: "Proportional Navigation"
  difficulty: medium
  tags: ["guidance"]

- id: GROUND-009
  field: ground
  question: "How is terrain data represented (DEM/DTED) and what resolution matters?"
  expected_answer:
    short: "Terrain elevation is stored as gridded DEM/DTED; grid spacing controls slope/LOS accuracy and affects planning and sensor modeling."
    must_include: ["DEM", "grid", "resolution"]
  required_evidence:
    - doc_id: ground_terrain_data_guide_2022
      section_path_contains: "DEM"
  difficulty: easy
  tags: ["terrain"]

- id: SENSOR-015
  field: sensor
  question: "What is PRF trade-off (range ambiguity vs Doppler ambiguity)?"
  expected_answer:
    short: "Higher PRF reduces Doppler ambiguity but increases range ambiguity; lower PRF does the opposite."
    must_include: ["PRF", "range ambiguity", "Doppler ambiguity"]
  required_evidence:
    - doc_id: sensor_radar_theory_2024
      section_path_contains: "PRF"
  difficulty: easy
  tags: ["prf"]
```

---

# Step-by-step execution checklist (the “next steps” in order)

1. **Finalize the 150 FAQ list** (use Step 1 as baseline; edit for your org’s actual queries).
2. **Create coverage_map.yaml** linking every FAQ to ≥2 documents you intend to collect.
3. **Collect ~20 docs per field** by **document type mix** (Step 2) and record basic doc metadata.
4. **Ingest + chunk** using heading-aware rules (Step 3). Attach metadata to every chunk.
5. **Deduplicate** exact + near-duplicate (Step 3.3) before indexing.
6. **Index & retrieve** (baseline retriever) and run retrieval-only evaluation (Step 4).
7. **Add reranker** and re-run evaluation; compare recall/MRR deltas (Step 4).
8. **Run end-to-end answer evaluation** with “cite-or-abstain” policy (Step 4.1).
9. **Analyze failures** with gap tags (R1–R5, G1–G2) (Step 5).
10. **Targeted collection or re-chunk** only where gaps exist; no random additions (Step 5).
11. Iterate until thresholds are met, then **freeze a release** (dataset + index snapshot + metrics).

---

## Optional (but high value) add-ons for Qwen2.5 1.5B
- Query rewrite layer: synonym expansion per field (e.g., “azimuth resolution” ↔ “cross-range resolution”)
- Field-aware routing: classify query → field → retrieve only within that field
- “Concept Sheets”: 1–2 page curated summaries per topic to reduce multi-hop failures

---

**End of document**
