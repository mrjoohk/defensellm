# 06_web_ui_design_suggestions.md — Web UI Design Suggestions

## Goal

Build a web UI that makes the current defense-LLM system easier to operate while preserving the system's strengths:

- evidence-first answers (citations)
- strong security signaling (clearance / labels)
- auditability (`request_id`, versions, response hash)
- support for both RAG and structured DB query flows

---

## Recommended Product Shape (MVP)

Use a **two-surface UI** instead of a single generic chat page:

1. **Operator Workspace** (day-to-day use)
2. **Audit & Trace Console** (verification / debugging / compliance)

This matches your implemented behavior better than a plain chatbot UI.

---

## Information Architecture

### 1. Operator Workspace (Primary)

Purpose: Ask questions, see answers, verify evidence, understand why a request failed.

Main panels:

- **Left rail**
  - New Query
  - Document Ingestion
  - Audit Console
  - Saved Sessions (optional)
- **Center panel**
  - Query input
  - Conversation / result history
  - Answer card
- **Right panel (Inspector)**
  - Citations
  - Request metadata
  - Raw JSON (toggle)

### 2. Document Ingestion

Purpose: Upload/index docs with metadata required by your pipeline.

Form fields (map to current CLI/index flow):

- file upload
- `doc_id`
- `doc_rev`
- `title`
- `field` (`air`, `weapon`, `ground`, `sensor`, `comm`)
- `security_label` (`PUBLIC`, `INTERNAL`, `RESTRICTED`, `SECRET`)
- chunk settings (`max_tokens`, `overlap`) in an "Advanced" accordion

Show result summary:

- chunks indexed
- index version used/generated
- file hash
- success/error status

### 3. Audit & Trace Console

Purpose: Quickly inspect request outcomes and prove traceability.

Views:

- **Search by `request_id`**
- **Recent requests table**
- **Detail drawer**
  - request metadata
  - model/index versions
  - citations list
  - response hash
  - error code (if any)

This is especially useful for IF-004 and failure scenarios (IF-005).

---

## Screen Design Suggestions (Web)

## A. Query Screen Layout

Use an "analyst console" style instead of a consumer chat aesthetic.

- **Top status strip**
  - Active user role / clearance
  - DB path / index version (environment badge)
  - model badge (e.g., `qwen2.5-1.5b-instruct`)
- **Prompt composer**
  - text area
  - field filters (multi-select)
  - `top_k`
  - "Show citations" toggle
  - "Run" button
- **Answer card**
  - answer text
  - security label badge
  - error badge (if present)
  - expanders for citations / metadata / raw response

### Why this works for your system

Your backend returns a rich standard response schema, not just text. The UI should surface:

- `request_id`
- `citations`
- `security_label`
- `version` (`model`, `index`, `db`)
- `hash`

These should be first-class UI elements, not hidden debug data.

---

## B. Citation UX (Important)

Citations are a core trust feature. Treat them as a dedicated component.

For each citation row:

- `doc_id` + `doc_rev`
- page / section
- snippet preview (collapsed by default)
- `snippet_hash`
- copy buttons (`doc_id`, `snippet_hash`)

Interaction ideas:

- click citation chip in answer -> highlight matching citation row
- "Compare snippets" toggle if multiple citations are returned
- "Copy evidence bundle" button (copies `request_id` + citations + response hash)

---

## C. Error State UX (Must-Have)

Your executor returns structured error codes. The UI should render them explicitly.

- `E_AUTH`
  - red refusal banner
  - explain that access was denied
  - show no hidden content
- `E_VALIDATION`
  - amber system error banner
  - suggest retry or admin review
- `E_INTERNAL`
  - red system failure banner
  - include `request_id` for support trace

Do not collapse all failures into "something went wrong."

---

## D. Security-Sensitive UX Patterns

- Show current user `role` and `clearance` prominently at all times.
- Color-code security labels consistently:
  - `PUBLIC` = gray
  - `INTERNAL` = blue
  - `RESTRICTED` = amber
  - `SECRET` = red
- If results are empty, display a neutral message that covers both cases:
  - no relevant documents
  - insufficient access

This matches your backend behavior and avoids leakage.

---

## Visual Direction (Non-generic)

Suggested style: **Mission Console / Evidence Desk**

- Background: warm off-black or desaturated slate with subtle grid texture
- Accent colors: cyan (data), amber (warning), red (restricted), green (success)
- Typography pairing:
  - UI labels: `IBM Plex Sans` or `Space Grotesk`
  - IDs / hashes / JSON: `IBM Plex Mono`
- Cards: sharp corners or slightly rounded (4-6px), not soft consumer UI bubbles
- Motion:
  - staggered reveal for citations
  - slide-in inspector panel
  - reduced-motion support for accessibility

This fits defense/audit tooling better than a default SaaS chat template.

---

## Suggested Web App Architecture

### Option 1 (Fastest MVP): Streamlit/Gradio-style Internal Tool

Pros:

- fastest path to usable UI
- easy file upload + forms
- good for internal demos

Cons:

- weaker control over complex inspector/audit interactions
- harder to scale into a polished operator console

### Option 2 (Recommended): React Frontend + FastAPI Backend

Frontend:

- React + Vite
- component library only if it does not fight the console aesthetic
- JSON viewer + table components

Backend (thin API wrapper over your modules):

- `POST /api/query`
- `POST /api/index`
- `GET /api/audit/{request_id}`
- `GET /api/audit/recent`
- `GET /api/health`

Why:

- cleanly separates UI from your CLI
- easier to add auth/session handling later
- better fit for audit console and role-aware UI

---

## Backend API Shape (Mapping Existing Logic)

### `POST /api/query`

Request:

```json
{
  "question": "KF-21의 최대 순항 고도는?",
  "user": { "role": "analyst", "clearance": "INTERNAL", "user_id": "u-001" },
  "field_filters": ["air"],
  "top_k": 5,
  "show_citations": true
}
```

Response:

- reuse your existing standard response schema as-is

### `POST /api/index`

Multipart form + metadata fields matching current CLI options.

Response should include:

- indexing summary
- document metadata
- index version
- status

### `GET /api/audit/{request_id}`

Return the most recent audit record from `fetch_by_request_id`.

---

## UX Features Worth Adding Early

1. **Raw JSON toggle** on every response
2. **Copy request bundle** (`request_id`, hash, versions, citations)
3. **Audit lookup shortcut** from each answer card
4. **Field/security filter chips** in the query composer
5. **Session export** (JSON) for test/demo evidence

These improve debugging and stakeholder demos immediately.

---

## MVP Build Order (Practical)

1. Query page with answer + citations + metadata panel
2. Document ingestion page (upload + metadata + indexing result)
3. Audit lookup page (`request_id` search)
4. Recent audit table
5. Authentication / role switching UI (real auth later, mock first)

---

## Common UI Mistakes to Avoid (For This System)

- Building only a chat bubble interface and hiding citations/metadata
- Hiding security labels or current clearance
- Treating audit fields as backend-only debug data
- Returning plain-text errors in UI without error-code badges
- Mixing ingestion/admin actions into the same panel as query controls

---

## Summary Recommendation

For this project, design the web UI as an **operator console with an evidence inspector**, not a generic chatbot. Your strongest differentiators are:

- citations
- security controls
- audit traceability
- versioned responses

If the UI surfaces those cleanly, the system will feel much more reliable and easier to validate in demos and internal use.
