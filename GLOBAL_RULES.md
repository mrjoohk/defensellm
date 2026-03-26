# CLAUDE.md
## Execution Instructions for Claude Code

You are tasked with implementing a Defense-domain sLLM Agent System according to requirements.md.

You MUST follow the exact execution order below.

---
# WORKFLOW RULES

### Rule 1 — Review Before Creating Output
> Before creating any final deliverable (document, file), first share the analysis/investigation summary with the user and wait for approval.

**Flow**: Start task → Perform analysis → Present findings to user → Await approval → Create output

### Rule 2 — Preserve Analysis as MD Files
> Save all analysis/investigation content created during tasks as MD files for reuse in future tasks.

**Filename convention**: `YYMMDD_HHMM_[description].md`
Example: `260318_1430_uf_status_analysis.md`

### Rule 3 — State Judgment Rationale
> Every decision, choice, or recommendation must include the rationale (판단 근거).

**Apply**: Include a "판단 근거:" section in all analysis MD files and user reports.

### Rule 4 — File Creation Log
> All files created in the working folder must be logged in `0.FilesUpdate.xlsx`.
> **If `0.FilesUpdate.xlsx` does not exist, create it first, then record the entry.**

| Column | Content |
|--------|---------|
| 일시 | YYYY-MM-DD HH:MM |
| 파일명 | Created filename |
| 요청 요약 | Core content of user's request |

### Rule 5 — Output Format Standard
> Deliverables containing tables or figures must be created as `.docx`.

| Condition | Format |
|-----------|--------|
| Contains table or figure | `.docx` |
| Text-focused analysis/memo | `.md` |
| Data/numeric-focused | `.xlsx` |
| Slide presentation | `.pptx` |

### Rule 6 — Directory for Review Documents
> All files (docx, ppt, xlsx, md) created during analysis/investigation phases must be saved in the `review_docs` directory.
> **If `review_docs` does not exist, create it first.**

**Apply to**: Any file produced during analysis, review, or investigation steps (before user approval).

### Rule 7 — Directory for Output Documents
> All files (docx, ppt, xlsx, md) created as final responses, results, or action outputs must be saved in the `output_docs` directory.
> **If `output_docs` does not exist, create it first.**

**Apply to**: Any file produced as a deliverable, response, or remediation result (after user approval).

### Rule 8 — Prompt & Response Log
> Every user request prompt and the agent's corresponding response/result must be recorded in order in `1.PromptsUpdate.xlsx`.
> **If `1.PromptsUpdate.xlsx` does not exist, create it first.**

| Column | Content |
|--------|---------|
| 일시 | YYYY-MM-DD HH:MM |
| 요청 프롬프트 | Full text of the user's request |
| 응답/결과/대처 | Summary of the agent's response or action taken |

### Workflow Summary
```
Receive request
  → [Rule 8] Log user prompt to 1.PromptsUpdate.xlsx
  → Perform analysis/investigation
  → [Rule 3] Summarize with judgment rationale
  → [Rule 6] Save analysis files to review_docs/
  → [Rule 1] Present to user for review → Await approval
  → Create output
  → [Rule 7] Save output files to output_docs/
  → [Rule 2] Save analysis as MD (yymmdd_hhmm_*.md)
  → [Rule 4] Update 0.FilesUpdate.xlsx
  → [Rule 8] Log agent response to 1.PromptsUpdate.xlsx
```
