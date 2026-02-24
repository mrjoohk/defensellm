# CLAUDE.md
## Execution Instructions for Claude Code

You are tasked with implementing a Defense-domain sLLM Agent System according to requirements.md.

You MUST follow the exact execution order below.

---

# PHASE 1 — Requirements Formalization

1. Read requirements.md.
2. Convert all design-level requirements into structured REQ entries.
3. Create file:
   docs/01_requirements_analysis.md

Each REQ must contain:
- REQ-ID
- Description
- Input
- Output
- Success Criteria
- Validation Method
- Priority

No ambiguous wording allowed.

---

# PHASE 2 — Unit Function Decomposition

1. Decompose REQs into Unit Functions (UF).
2. Each UF must be implementable as an isolated Python function or class.

Create:
docs/02_unit_functions.md

Each UF must contain:
- UF-ID
- Module
- Purpose
- Input/Output Schema
- Exceptions
- Dependencies
- Related REQ-ID
- Test Points

Modules must include:
config
security
knowledge
rag
agent
serving
audit
eval

---

# PHASE 3 — Unit Tests & Coverage

1. Create test skeletons under tests/unit/
2. Every UF must have:
   - at least 1 success test
   - at least 1 failure test
3. LLM must be mocked.
4. No external services allowed.

Create:
docs/03_unit_test_coverage.md

Coverage Targets:
- Overall ≥ 70%
- Security/Audit ≥ 80%

---

# PHASE 4 — Integration Function Design

Combine UFs into Integration Functions (IF).

Create:
docs/04_integration_functions.md

Required IF scenarios:
1. Document upload → indexing → query → citation response
2. Structured DB query → constraint enforcement → cited response
3. Unauthorized search → blocked result
4. Audit logging verification
5. Tool schema violation → safe failure

Each IF must specify:
- Scenario
- Used UFs
- Input/Output
- Success Criteria
- Security Conditions

---

# PHASE 5 — Integration Tests

1. Implement integration tests in tests/integration/
2. Use SQLite temporary DB
3. Use mock LLM
4. Verify:
   - citation presence
   - security enforcement
   - audit log creation

Create:
docs/05_integration_test_coverage.md

---

# Implementation Rules

- No network access.
- No real model loading required.
- Serving layer must use adapter pattern.
- Planner must be rule-based.
- Executor must validate schema before responding.
- All outputs must follow the standard response schema in requirements.md.
- Use pytest + coverage.
- Provide README with reproducible commands.

---

# Final Output Requirements

At completion, provide:
1. File list created
2. pytest summary
3. coverage summary
4. REQ ↔ UF ↔ IF trace table
5. Upgrade notes for switching to 7B+

You must not skip any phase.
You must not collapse phases.
You must not introduce non-deterministic behavior.

---
