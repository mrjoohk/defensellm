# Testing Manual — Defense LLM Agent API (Phase 5)

**Version**: 0.5.0
**Date**: 2026-03-26
**Scope**: FastAPI `/agent` endpoint, Web UI, 50 JSON scenario files

---

## Table of Contents

1. [Environment Requirements](#1-environment-requirements)
2. [Starting the FastAPI Server](#2-starting-the-fastapi-server)
3. [Web UI Usage](#3-web-ui-usage)
4. [REST API Reference](#4-rest-api-reference)
5. [Running Scenario Files](#5-running-scenario-files)
6. [Response Structure Guide](#6-response-structure-guide)
7. [Interpreting Decision Support Output](#7-interpreting-decision-support-output)
8. [Pass / Fail Criteria](#8-pass--fail-criteria)
9. [Automated Test Suite](#9-automated-test-suite)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Environment Requirements

### Python Environment

```bash
conda activate dllm          # or: source activate dllm
python --version             # Python 3.10+
```

### Install Dependencies

```bash
pip install -e . --break-system-packages
pip install httpx --break-system-packages   # FastAPI TestClient
```

### Verify FastAPI is Available

```bash
python -c "import fastapi; print(fastapi.__version__)"
python -c "import uvicorn; print(uvicorn.__version__)"
```

---

## 2. Starting the FastAPI Server

### Basic Start (Development)

```bash
cd /path/to/defensellm

uvicorn defense_llm.serving.api:app --reload --host 0.0.0.0 --port 8000
```

### With Custom Port

```bash
uvicorn defense_llm.serving.api:app --port 9000 --log-level info
```

### Production Start (no reload)

```bash
uvicorn defense_llm.serving.api:app --host 0.0.0.0 --port 8000 --workers 1
```

### Verify Server is Running

```bash
curl http://localhost:8000/health
# Expected: {"status":"ok","executor_ready":true}
```

The server log will show:
```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

---

## 3. Web UI Usage

### Open the Interface

Navigate to **http://localhost:8000** in any browser.

### Interface Layout

```
┌─────────────────────────────────────────────────────────┐
│  DEFENSE LLM  │  Agent Decision Support Interface        │
├──────────────────────┬──────────────────────────────────┤
│  LEFT PANEL          │  RIGHT PANEL                     │
│  ─ Query input       │  ─ Response display              │
│  ─ JSON upload zone  │  ─ Meta strip (request_id, etc.) │
│  ─ Paste JSON area   │  ─ Answer card                   │
│  ─ Options           │  ─ Tool Call Log (collapsible)   │
│  ─ User Context      │  ─ Citations (collapsible)       │
│  ─ [Run Agent] btn   │                                  │
└──────────────────────┴──────────────────────────────────┘
```

### Uploading a Battle Context JSON File

**Method 1 — File Upload:**
1. Click the upload zone (📂 area) or drag a `.json` file onto it.
2. The file name appears in green (e.g., `✓ SCN-001_ARMOR_THREAT_ASSESS.json`).
3. The JSON content is automatically reflected in the "Paste JSON" area.

**Method 2 — Paste JSON:**
1. Click "▶ Paste JSON directly" to expand the textarea.
2. Paste a `BattleSituationPrompt` JSON string.
3. Valid JSON turns the indicator green (`✓ JSON valid (pasted)`).

### Scenario Files Location

All 50 pre-built scenario files are in:
```
tests/scenarios/SCN-{NNN}_{THREAT_TYPE}_{INTENT}.json
```

Example files to test:
| File | Scenario |
|------|---------|
| `SCN-001_ARMOR_THREAT_ASSESS.json` | ARMOR threat, HOLD ROE |
| `SCN-019_ARMOR_COA_RECOMMEND.json` | ARMOR, FIRE_AT_WILL ROE |
| `SCN-027_MIXED_COMPOSITE.json` | COMPOSITE intent, URBAN terrain |
| `SCN-035_ARMOR_FIRES_RECOMMEND.json` | Fires plan with 3 assets |
| `SCN-049_MISSILE_ROE_CHECK.json` | TTL 5-min urgent |
| `SCN-050_CYBER_INTEL_REQUEST.json` | Cyber threat edge case |

### Options

| Option | Default | Effect |
|--------|---------|--------|
| **Agent Mode** | ✓ ON | Enables ReAct agent loop (tool calls visible in Tool Call Log) |
| **Composite Chain** | OFF | Triggers `decision_support_composite` — runs all 5 tools in one chain |

### Keyboard Shortcut

Press **Ctrl + Enter** in the Query field to submit without clicking.

---

## 4. REST API Reference

### POST `/agent`

Accepts JSON body. Returns agent response.

**Request Body:**

```json
{
  "query": "현재 위협 수준을 평가하고 행동 방책을 제시하라.",
  "battle_situation": { ...BattleSituationPrompt... },
  "agent_mode": true,
  "use_composite": false,
  "user_context": {
    "role": "analyst",
    "clearance": "SECRET",
    "user_id": "test_user"
  }
}
```

**Field descriptions:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | ✓ | User query text |
| `battle_situation` | object | - | BattleSituationPrompt JSON |
| `agent_mode` | bool | - | Default: `true` |
| `use_composite` | bool | - | Triggers composite chain; default: `false` |
| `user_context` | object | - | role / clearance / user_id |

**cURL Example:**

```bash
curl -X POST http://localhost:8000/agent \
  -H "Content-Type: application/json" \
  -d '{
    "query": "현재 위협 수준을 평가하라.",
    "battle_situation": {
      "scenario_id": "SCN-TEST",
      "timestamp": "2026-03-26T06:00:00Z",
      "threat": {
        "type": "ARMOR", "count": 12,
        "movement": "ADVANCING", "confidence": 0.85,
        "description": "12대 전차 부대 접근"
      },
      "friendly_forces": {
        "unit_id": "1BN", "unit_type": "MECHANIZED",
        "strength": "COMPANY", "readiness": "READY"
      },
      "query": {
        "intent": "THREAT_ASSESS",
        "text": "위협 수준을 평가하라.",
        "roe_level": "RETURN_FIRE"
      },
      "classification": "CONFIDENTIAL"
    }
  }'
```

**Python requests Example:**

```python
import requests, json

url = "http://localhost:8000/agent"
scenario = json.load(open("tests/scenarios/SCN-001_ARMOR_THREAT_ASSESS.json"))

resp = requests.post(url, json={
    "query": "위협 평가 및 행동 방책을 제시하라.",
    "battle_situation": scenario,
    "agent_mode": True,
    "use_composite": False,
})
print(resp.json()["answer"])
```

### POST `/agent/upload`

Accepts `multipart/form-data` for JSON file upload.

```bash
curl -X POST "http://localhost:8000/agent/upload?query=위협을+평가하라&agent_mode=true" \
  -F "battle_situation_file=@tests/scenarios/SCN-001_ARMOR_THREAT_ASSESS.json"
```

### GET `/health`

```bash
curl http://localhost:8000/health
# {"status":"ok","executor_ready":true}
```

### GET `/docs`

FastAPI auto-generated Swagger UI at **http://localhost:8000/docs**

---

## 5. Running Scenario Files

### Run a Single Scenario

```bash
python - << 'EOF'
import requests, json, sys

url = "http://localhost:8000/agent"
fpath = "tests/scenarios/SCN-001_ARMOR_THREAT_ASSESS.json"

scenario = json.load(open(fpath, encoding="utf-8"))
resp = requests.post(url, json={
    "query": scenario["query"]["text"],
    "battle_situation": scenario,
    "agent_mode": True,
}).json()

print(f"[{resp['error_code'] or 'OK'}] {resp['answer'][:120]}")
print(f"  Tool calls: {len(resp['tool_call_log'])}")
EOF
```

### Run All 50 Scenarios (Batch)

```bash
python - << 'EOF'
import requests, json, os, time

url = "http://localhost:8000/agent"
scenario_dir = "tests/scenarios"
results = []

files = sorted(os.listdir(scenario_dir))
for fname in files:
    if not fname.endswith(".json"):
        continue
    fpath = os.path.join(scenario_dir, fname)
    scenario = json.load(open(fpath, encoding="utf-8"))
    try:
        resp = requests.post(url, json={
            "query": scenario["query"]["text"],
            "battle_situation": scenario,
            "agent_mode": True,
        }, timeout=30).json()
        status = resp.get("error_code") or "OK"
        tool_n = len(resp.get("tool_call_log", []))
        results.append((fname, status, tool_n))
        print(f"[{status:12s}] {fname}  tool_calls={tool_n}")
    except Exception as e:
        results.append((fname, "EXCEPTION", 0))
        print(f"[EXCEPTION  ] {fname}  {e}")

ok = sum(1 for r in results if r[1] == "OK")
print(f"\n{'='*60}")
print(f"PASSED: {ok}/{len(results)}  FAILED: {len(results)-ok}/{len(results)}")
EOF
```

### Run Composite Chain Scenarios

```bash
python - << 'EOF'
import requests, json

url = "http://localhost:8000/agent"
composite_files = [
    "tests/scenarios/SCN-027_MIXED_COMPOSITE.json",
    "tests/scenarios/SCN-035_ARMOR_FIRES_RECOMMEND.json",
]
for fpath in composite_files:
    scenario = json.load(open(fpath, encoding="utf-8"))
    resp = requests.post(url, json={
        "query": scenario["query"]["text"],
        "battle_situation": scenario,
        "agent_mode": True,
        "use_composite": True,
    }, timeout=30).json()
    print(f"\n=== {scenario['scenario_id']} ===")
    print(f"answer: {resp['answer'][:100]}")
    print(f"tool_calls: {[t['tool_name'] for t in resp['tool_call_log']]}")
EOF
```

---

## 6. Response Structure Guide

```json
{
  "request_id": "a1b2c3d4-...",
  "answer": "분석 완료. 전술 상황을 검토하였습니다.",
  "citations": [],
  "error_code": null,
  "tool_call_log": [
    {
      "turn": 1,
      "tool_name": "threat_assess",
      "args_summary": "{'threat_type': 'ARMOR', 'count': 12, ...}",
      "result_summary": "{'threat_level': 'HIGH', 'threat_score': 0.84, ...}",
      "error": null
    }
  ],
  "battle_context_parsed": true
}
```

| Field | Type | Description |
|-------|------|-------------|
| `request_id` | string | UUID for audit tracing |
| `answer` | string | Agent's final text response |
| `citations` | array | RAG document citations (empty when no docs indexed) |
| `error_code` | string \| null | `null` = success; `E_AUTH` / `E_VALIDATION` / `E_INTERNAL` / `E_LOOP_LIMIT` = failure |
| `tool_call_log` | array | Per-turn tool call trace |
| `battle_context_parsed` | bool | `true` if `battle_situation` was successfully parsed |

### error_code Values

| Code | Meaning | Action |
|------|---------|--------|
| `null` | Success | — |
| `E_AUTH` | Access denied (RBAC/clearance) | Check user_context clearance |
| `E_VALIDATION` | Tool call schema invalid | Check tool arguments |
| `E_INTERNAL` | Unexpected exception | Check server logs |
| `E_LOOP_LIMIT` | Agent exceeded max_turns (10) | Query too complex; simplify or increase max_turns |

---

## 7. Interpreting Decision Support Output

When `agent_mode=True` and `battle_situation` is provided, the agent will call decision support tools based on the `query.intent` field. The `tool_call_log` shows which tools were called and their results.

### Typical Tool Call Sequences by Intent

| `query.intent` | Expected Tool Calls |
|---|---|
| `THREAT_ASSESS` | `threat_assess` |
| `COA_RECOMMEND` | `threat_assess` → `coa_generate` |
| `FIRES_RECOMMEND` | `threat_assess` → `fires_plan` |
| `ROE_CHECK` | `roe_check` |
| `INTEL_REQUEST` | `ipb_summary` |
| `COMPOSITE` | `threat_assess` → `ipb_summary` → `coa_generate` → `roe_check` |
| `COMPOSITE` + `use_composite=true` | `decision_support_composite` (single call) |

### Reading threat_assess Output

```json
{
  "threat_level": "HIGH",
  "threat_score": 0.84,
  "roe_constraint": "RETURN_FIRE: 교전 허용",
  "recommended_actions": ["화력 집중 준비", "방어 진지 강화"],
  "confidence_note": "신뢰도 적정"
}
```

**threat_level scale:** `MINIMAL` → `LOW` → `MEDIUM` → `HIGH` → `CRITICAL`

### Reading coa_generate Output

```json
{
  "coas": [
    {
      "coa_id": "COA-A",
      "name": "적극 방어 + 화력 집중",
      "success_probability": 0.72,
      "roe_compliant": true,
      "advantages": ["적 진격 조기 저지"],
      "disadvantages": ["자산 소모율 증가"]
    }
  ],
  "recommended_coa": "COA-A",
  "num_coas_generated": 3
}
```

### Reading decision_support_composite Output (Composite Chain)

When `use_composite=true`, the tool_call_log will contain a single `decision_support_composite` call whose result includes all 5 tool outputs:

```json
{
  "package_type": "DECISION_SUPPORT_COMPOSITE",
  "execution_chain": ["threat_assess","ipb_summary","coa_generate","roe_check","fires_plan"],
  "errors": [],
  "threat_assessment": { ... },
  "ipb_summary": { ... },
  "coa_recommendation": { ... },
  "roe_validation": { ... },
  "fires_plan": { ... }
}
```

---

## 8. Pass / Fail Criteria

### Per-Scenario Pass Criteria

A scenario **PASSES** if all of the following are true:

| # | Criterion | Check |
|---|-----------|-------|
| P-1 | HTTP status code is `200` | `resp.status_code == 200` |
| P-2 | `error_code` is `null` | `resp["error_code"] is None` |
| P-3 | `answer` is non-empty string | `len(resp["answer"]) > 0` |
| P-4 | `battle_context_parsed` is `true` when JSON provided | `resp["battle_context_parsed"] == True` |
| P-5 | No `error` field in any `tool_call_log` entry | all `t["error"] is None` |

### Batch Test Target

- **All 50 scenarios:** `≥ 48/50` pass (96%) — allows for 2 edge-case failures
- **Composite chain scenarios (D-group, 6 files):** `6/6` pass
- **Edge case scenarios (F-group, 4 files):** `≥ 3/4` pass

### Automated Test Assertions (test_api.py)

```bash
python -m pytest tests/unit/test_api.py -v
```

---

## 9. Automated Test Suite

### Run Unit Tests (no server required)

```bash
# Full test suite
python -m pytest tests/ -v -q

# API tests only (uses FastAPI TestClient — no server needed)
python -m pytest tests/unit/test_api.py -v

# All Phase 5 related
python -m pytest tests/unit/test_api.py tests/unit/test_commander_interface.py -v
```

### Coverage Report

```bash
python -m pytest tests/ --cov=defense_llm --cov-report=term-missing -q
```

Expected coverage targets (from CLAUDE.md Phase 3):
- Overall: ≥ 70%
- Security/Audit: ≥ 80%

---

## 10. Troubleshooting

### Server won't start: `ModuleNotFoundError: No module named 'defense_llm'`

```bash
cd /path/to/defensellm
pip install -e . --break-system-packages
```

### `422 Unprocessable Entity` on `/agent`

The `battle_situation` JSON failed schema validation. Check:
- Required fields present: `scenario_id`, `timestamp`, `threat`, `friendly_forces`, `query`
- `threat.type` is one of: `ARMOR / INFANTRY / AIR / NAVAL / MISSILE / DRONE / CYBER / MIXED`
- `query.intent` is one of: `THREAT_ASSESS / COA_RECOMMEND / FIRES_RECOMMEND / INTEL_REQUEST / ROE_CHECK / LOGISTICS_CHECK / COMPOSITE`
- `query.roe_level` is one of: `HOLD / RETURN_FIRE / FIRE_AT_WILL / WEAPONS_FREE`

### `503 Service Unavailable`

Executor failed to initialize. Check:
- SQLite temp directory is accessible
- No import errors in startup log

### Web UI: "JSON invalid" on paste

- Ensure the JSON is valid (use a JSON validator like https://jsonlint.com)
- Check that string values use double quotes, not single quotes
- Check there are no trailing commas

### Agent returns `E_LOOP_LIMIT`

The query triggered more than 10 agent turns. Possible causes:
- MockLLM does not terminate the loop (set `tool_call_sequence=[]` for fast termination)
- For production: increase `max_agent_turns` in `Executor.__init__`

### Port Already in Use

```bash
lsof -i :8000       # Find process using port 8000
kill -9 <PID>       # Kill it
uvicorn defense_llm.serving.api:app --port 8001   # Or use different port
```
