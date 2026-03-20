# requirements.md
## Defense Domain sLLM/Agent System Design
### Target: Qwen2.5 1.5B (Single GPU) → Upgradeable to Higher Models

---

# 1. System Overview

This document defines the system design for a defense-domain knowledge and agent system built on:

- Initial model: **Qwen2.5 1.5B Instruct**
- Deployment: **Single GPU, on-premise**
- Architecture principle:
  - Knowledge resides in **RAG + Structured DB + Metadata**
  - LLM handles **language generation, tool orchestration, formatting**
  - Planner is **rule-based**
  - Executor is **LLM-driven**
- Must be **upgrade-ready** for 7B / 14B / 32B models without architectural redesign

---

# 2. System Architecture

## 2.1 Core Components

1. Model Serving Layer
   - OpenAI-compatible API abstraction
   - Mockable adapter layer
   - Model swap capability (1.5B → 7B+)

2. Knowledge Layer
   - Structured DB (platforms, weapons, systems, constraints)
   - Document repository (PDF/text + metadata)
   - Glossary (terminology normalization)

3. Retrieval Layer (RAG)
   - Hybrid search (BM25 + Vector)
   - Metadata filtering (field, program, block, security_label)
   - Citation packaging (page/section/snippet_hash)

4. Agent Layer
   - Rule-based Planner
   - LLM Executor
   - Tool schema validation
   - Deterministic failure handling

5. Security Layer
   - RBAC / ABAC enforcement
   - Output masking rules
   - Pre-search and post-search filtering

6. Audit Layer
   - request_id generation
   - Model version tracking
   - Index version tracking
   - Citation logging
   - Response hashing

7. Evaluation Layer
   - Deterministic evaluation runner
   - JSON report generation
   - Regression-ready structure

---

# 3. Functional Requirement Categories

## 3.1 Knowledge Management

- Must support field-level separation:
  - air
  - weapon
  - ground
  - sensor
  - comm
- Must support:
  - version tracking
  - document revision control
  - metadata validation
  - hash-based integrity checks

## 3.2 RAG Requirements

- Hybrid retrieval required
- Citation must include:
  - doc_id
  - doc_rev
  - page or section
  - snippet_hash
- No answer without citation unless explicitly declared insufficient evidence

## 3.3 Agent Requirements

- Planner must classify query types:
  - STRUCTURED_KB_QUERY
  - DOC_RAG_QUERY
  - MIXED_QUERY
  - SECURITY_RESTRICTED
  - UNKNOWN
- Executor must:
  - Validate tool schema
  - Validate security level
  - Apply response template

## 3.4 Security Requirements

- Unauthorized user must receive:
  - empty search result OR explicit refusal
- Output masking must apply to:
  - coordinates
  - frequency values
  - system identifiers

## 3.5 Audit Requirements

Each request must log:
- request_id
- model version
- index version
- citations used
- response hash

## 3.6 Upgrade Requirements

Model replacement must require changes only in:
- serving layer
- optional prompt tuning

All other layers must remain unchanged.

---

# 4. Non-Functional Requirements

- Deterministic testing (no external dependency)
- Unit test coverage target ≥ 70%
- Security & audit modules ≥ 80%
- Integration scenario success rate = 100%
- No external network access required

---

# 5. Standard Response Schema

All tool and API responses must follow:

{
  "request_id": "uuid",
  "data": {},
  "citations": [],
  "security_label": "PUBLIC|INTERNAL|RESTRICTED|SECRET",
  "version": {
    "model": "qwen2.5-1.5b-instruct",
    "index": "idx-YYYYMMDD-hhmm",
    "db": "schema-v1"
  },
  "hash": "sha256"
}

---

# 6. Acceptance Conditions

The system is accepted only if:

- All modules are testable offline
- Audit logging verified
- Security restrictions verified
- Citation validation enforced
- Model adapter swappable without modifying RAG/Agent logic

---
