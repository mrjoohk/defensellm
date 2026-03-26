"""Defense-LLM CLI — command-line interface for the sLLM/Agent system.

Usage:
  defense-llm query  "질문" [options]
  defense-llm index  <file> [options]
  defense-llm db     init   [options]
  defense-llm eval   [options]
  defense-llm config check  [options]
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Optional

import click

# ---------------------------------------------------------------------------
# Common option helpers
# ---------------------------------------------------------------------------

_DB_OPTION = click.option(
    "--db-path", default="./data/defense.db", show_default=True,
    envvar="DEFENSE_LLM_DB_PATH",
    help="SQLite DB 파일 경로",
)
_INDEX_OPTION = click.option(
    "--index-path", default="./data/index", show_default=True,
    envvar="DEFENSE_LLM_INDEX_PATH",
    help="인덱스 디렉토리 경로",
)
_LOG_OPTION = click.option(
    "--log-path", default="./data/logs", show_default=True,
    envvar="DEFENSE_LLM_LOG_PATH",
    help="로그 디렉토리 경로",
)


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------

@click.group()
@click.version_option("0.1.0", prog_name="defense-llm")
def cli():
    """Defense Domain sLLM/Agent 시스템 CLI

    \b
    Qwen2.5-1.5B-Instruct 기반 방산 도메인 지식 질의응답 시스템입니다.
    --mock 플래그를 사용하면 실제 모델 없이 테스트할 수 있습니다.
    """


# ---------------------------------------------------------------------------
# db init
# ---------------------------------------------------------------------------

@cli.group()
def db():
    """데이터베이스 관리 명령"""


@db.command("init")
@_DB_OPTION
def db_init(db_path: str):
    """SQLite DB 초기화 (테이블 생성, 스키마 버전 등록)"""
    from defense_llm.knowledge.db_schema import init_db

    _ensure_parent_dir(db_path)
    click.echo(f"DB 초기화 중: {db_path}")
    try:
        result = init_db(db_path)
        click.secho("✓ DB 초기화 완료", fg="green")
        click.echo(f"  생성된 테이블: {', '.join(result['tables_created'])}")
    except Exception as e:
        click.secho(f"✗ DB 초기화 실패: {e}", fg="red", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# index (document upload + chunking + indexing)
# ---------------------------------------------------------------------------

@cli.command("index")
@click.argument("file_path", type=click.Path(exists=True, readable=True))
@click.option("--doc-id", required=True, help="문서 고유 ID (예: DOC-001)")
@click.option("--doc-rev", default="v1.0", show_default=True, help="문서 버전")
@click.option("--title", default=None, help="문서 제목 (미입력 시 파일명 사용)")
@click.option(
    "--field", required=True,
    type=click.Choice(["air", "weapon", "ground", "sensor", "comm"], case_sensitive=False),
    help="도메인 필드",
)
@click.option(
    "--security-label", default="INTERNAL", show_default=True,
    type=click.Choice(["PUBLIC", "INTERNAL", "RESTRICTED", "SECRET"], case_sensitive=True),
    help="보안 등급",
)
@click.option("--max-tokens", default=512, show_default=True, help="청크당 최대 토큰 수")
@click.option("--overlap", default=64, show_default=True, help="청크 간 중복 토큰 수")
@click.option("--doc-type", default="unknown", help="문서 유형 (예: spec, glossary)")
@click.option("--system", default="", help="관련 체계")
@click.option("--subsystem", default="", help="관련 하위 체계")
@click.option("--date", default="", help="문서 날짜")
@click.option("--language", default="en", help="문서 언어")
@click.option("--source-uri", default="", help="문서 원본 URI")
@click.option(
    "--ocr", "force_ocr", is_flag=True, default=False,
    help="[PDF 전용] 텍스트 추출을 건너뛰고 항상 OCR을 강제 적용합니다.",
)
@click.option(
    "--ocr-lang", default="eng", show_default=True,
    help="[PDF 전용] Tesseract OCR 언어 코드 (예: eng, kor, kor+eng). "
         "한국어 문서는 kor 또는 kor+eng를 사용하십시오.",
)
@_DB_OPTION
@_INDEX_OPTION
def index_document(
    file_path: str,
    doc_id: str,
    doc_rev: str,
    title: Optional[str],
    field: str,
    security_label: str,
    max_tokens: int,
    overlap: int,
    doc_type: str,
    system: str,
    subsystem: str,
    date: str,
    language: str,
    source_uri: str,
    force_ocr: bool,
    ocr_lang: str,
    db_path: str,
    index_path: str,
):
    """문서 파일을 읽어 청킹·인덱싱합니다.

    \b
    지원 파일 형식:
      .txt / .md  — UTF-8 텍스트 직접 읽기
      .pdf        — opendataloader_pdf(Java 엔진)로 텍스트 추출,
                    이미지 기반 PDF는 Tesseract OCR 자동 적용

    \b
    예시:
      defense-llm index docs/manual.txt --doc-id DOC-001 --field air
      defense-llm index docs/scanned.pdf --doc-id DOC-002 --field air --ocr-lang kor+eng
      defense-llm index docs/image_only.pdf --doc-id DOC-003 --field air --ocr --ocr-lang kor
    """
    from defense_llm.knowledge.db_schema import init_db
    from defense_llm.knowledge.document_meta import register_document, compute_file_hash
    from defense_llm.rag.chunker import chunk_document
    from defense_llm.rag.indexer import DocumentIndex

    _ensure_parent_dir(db_path)
    _ensure_parent_dir(index_path + "/.keep")

    # Read file — PDF goes through pdf_parser, others are decoded as UTF-8
    content = Path(file_path).read_bytes()
    file_hash = compute_file_hash(content)
    resolved_title = title or Path(file_path).name

    if Path(file_path).suffix.lower() == ".pdf":
        from defense_llm.rag.pdf_parser import extract_text_from_pdf
        click.echo(f"  PDF 감지: opendataloader_pdf로 텍스트 추출 중…")
        try:
            text = extract_text_from_pdf(
                file_path,
                force_ocr=force_ocr,
                language=ocr_lang,
            )
            # Report whether OCR was applied (heuristic: check for OCR-style markers)
            from defense_llm.rag.pdf_parser import is_image_based_pdf
            if force_ocr:
                click.secho("  ✓ OCR 강제 적용 완료", fg="cyan")
            elif is_image_based_pdf(file_path):
                click.secho("  ✓ 이미지 기반 PDF → OCR 자동 적용 완료", fg="cyan")
            else:
                click.secho("  ✓ 텍스트 레이어 PDF → 직접 추출 완료", fg="green")
        except RuntimeError as e:
            click.secho(f"  ✗ PDF 추출 실패: {e}", fg="red", err=True)
            sys.exit(1)
    else:
        text = content.decode("utf-8", errors="replace")

    click.echo(f"문서 등록: {file_path}")
    click.echo(f"  doc_id={doc_id}, rev={doc_rev}, field={field}, label={security_label}")

    # Init DB (idempotent)
    init_db(db_path)

    # Register metadata
    try:
        register_document(db_path, {
            "doc_id": doc_id,
            "doc_rev": doc_rev,
            "title": resolved_title,
            "field": field,
            "security_label": security_label,
            "file_hash": file_hash,
        })
        click.secho("  ✓ 메타데이터 등록 완료", fg="green")
    except ValueError as e:
        if "E_CONFLICT" in str(e):
            click.secho(f"  ⚠ 이미 등록된 버전입니다: {e}", fg="yellow")
        else:
            click.secho(f"  ✗ 메타데이터 오류: {e}", fg="red", err=True)
            sys.exit(1)

    # Chunk document
    result = chunk_document(
        doc_id, doc_rev, text,
        security_label=security_label,
        doc_field=field,
        doc_type=doc_type,
        title=resolved_title,
        system=system,
        subsystem=subsystem,
        date=date,
        language=language,
        source_uri=source_uri,
        max_tokens=max_tokens,
        overlap=overlap,
    )
    click.echo(f"  청크 수: {result['indexed_count']}")

    # Load or create index
    if os.path.isdir(index_path) and os.path.isfile(os.path.join(index_path, "meta.json")):
        idx = DocumentIndex.load(index_path)
        click.echo("  기존 인덱스 로드됨")
    else:
        idx = DocumentIndex()

    idx.add_chunks(result["chunks"])
    
    import datetime
    ts = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M")
    idx.index_version = f"idx-{ts}"
    idx.save(index_path)
    click.secho(f"  ✓ 인덱싱 완료 → {index_path} (전체 청크: {idx.chunk_count()})", fg="green")


# ---------------------------------------------------------------------------
# query
# ---------------------------------------------------------------------------

@cli.command("query")
@click.argument("question")
@click.option("--role", default="analyst", show_default=True, help="사용자 역할")
@click.option(
    "--clearance", default="INTERNAL", show_default=True,
    type=click.Choice(["PUBLIC", "INTERNAL", "RESTRICTED", "SECRET"], case_sensitive=True),
    help="사용자 허가 등급",
)
@click.option(
    "--field", multiple=True,
    help="검색 도메인 필터 (복수 지정 가능: --field air --field weapon)",
)
@click.option(
    "--top-k", default=5, show_default=True,
    help="최대 검색 결과 수",
)
@click.option(
    "--mock", is_flag=True,
    help="실제 모델 대신 MockLLMAdapter 사용 (모델 미설치 환경)",
)
@click.option(
    "--model-id", default="Qwen/Qwen2.5-1.5B-Instruct", show_default=True,
    envvar="DEFENSE_LLM_MODEL_NAME",
    help="HuggingFace 모델 ID 또는 로컬 경로",
)
@click.option("--show-citations", is_flag=True, help="응답에 인용 출처 표시")
@click.option("--json-output", is_flag=True, help="결과를 JSON 형식으로 출력")
@_DB_OPTION
@_INDEX_OPTION
@_LOG_OPTION
def query_cmd(
    question: str,
    role: str,
    clearance: str,
    field: tuple,
    top_k: int,
    mock: bool,
    model_id: str,
    show_citations: bool,
    json_output: bool,
    db_path: str,
    index_path: str,
    log_path: str,
):
    """자연어 질문을 처리하고 근거 인용 답변을 반환합니다.

    \b
    예시:
      defense-llm query "KF-21 최대 순항 고도는?" --clearance INTERNAL
      defense-llm query "정비 절차" --field air --mock --show-citations
    """
    from defense_llm.knowledge.db_schema import init_db
    from defense_llm.rag.indexer import DocumentIndex
    from defense_llm.agent.planner_rules import classify_query, build_plan
    from defense_llm.agent.executor import Executor
    from defense_llm.audit.logger import AuditLogger
    from defense_llm.serving.mock_llm import MockLLMAdapter

    _ensure_parent_dir(db_path)
    _ensure_parent_dir(log_path + "/.keep")
    init_db(db_path)

    # Build security label filter from clearance
    _LEVEL = ["PUBLIC", "INTERNAL", "RESTRICTED", "SECRET"]
    user_level = _LEVEL.index(clearance)
    label_filter = _LEVEL[: user_level + 1]

    # Load index
    if not (os.path.isdir(index_path) and os.path.isfile(os.path.join(index_path, "meta.json"))):
        click.secho(
            f"⚠ 인덱스를 찾을 수 없습니다: {index_path}\n"
            "먼저 'defense-llm index' 명령으로 문서를 색인하십시오.",
            fg="yellow", err=True,
        )
        idx = DocumentIndex()
    else:
        idx = DocumentIndex.load(index_path)

    # LLM adapter
    if mock:
        llm = MockLLMAdapter(fixed_response="[MOCK] 질의에 대한 모의 응답입니다.")
        model_version = "mock-llm-0.0"
    else:
        from defense_llm.serving.qwen_adapter import Qwen25Adapter
        click.echo(f"모델 로딩 중: {model_id} (처음 실행 시 시간이 걸릴 수 있습니다…)")
        llm = Qwen25Adapter(model_id=model_id, preload=True)
        model_version = model_id

    audit = AuditLogger(db_path)
    executor = Executor(
        llm_adapter=llm,
        index=idx,
        db_path=db_path,
        audit_logger=audit,
        model_version=model_version,
        index_version=_index_version(index_path),
        index_path=index_path,
    )

    user_context = {
        "role": role,
        "clearance": clearance,
        "user_id": f"cli-{role}",
    }

    plan_context = {
        "query": question,
        "field_filter": list(field) if field else [],
        "security_label_filter": label_filter,
    }
    qt = classify_query(question, user_context)
    plan = build_plan(qt, {**plan_context, "top_k": top_k})

    request_id = str(uuid.uuid4())
    response = executor.execute(plan, user_context, request_id=request_id)

    if json_output:
        click.echo(json.dumps(response, ensure_ascii=False, indent=2))
        return

    # Human-readable output
    click.echo()
    _print_separator()
    click.secho("질문:", bold=True)
    click.echo(f"  {question}")
    click.echo()
    click.secho("답변:", bold=True)
    answer = response.get("data", {}).get("answer", "")
    click.echo(f"  {answer}")

    if response.get("error"):
        click.secho(f"\n  [오류] {response['error']}", fg="red")

    if show_citations and response.get("citations"):
        click.echo()
        click.secho("인용 출처:", bold=True)
        for i, c in enumerate(response["citations"], 1):
            click.echo(
                f"  [{i}] {c.get('doc_id')} rev={c.get('doc_rev')}"
                f" p.{c.get('page')} — {c.get('snippet', '')[:80]}…"
            )

    _print_separator()
    ver = response.get("version", {})
    click.secho(
        f"\n  request_id: {response.get('request_id')}\n"
        f"  model: {ver.get('model')}  index: {ver.get('index')}\n"
        f"  security_label: {response.get('security_label')}",
        dim=True,
    )


# ---------------------------------------------------------------------------
# eval
# ---------------------------------------------------------------------------

@cli.command("eval")
@click.option(
    "--samples", "samples_path",
    default="tests/fixtures/dummy_qa_samples.json", show_default=True,
    type=click.Path(exists=True), help="QA 샘플 JSON 파일 경로",
)
@click.option(
    "--output", "output_path",
    default="eval_report.json", show_default=True,
    help="평가 리포트 저장 경로",
)
@click.option("--mock", is_flag=True, help="MockLLMAdapter 사용")
@click.option("--model-id", default="Qwen/Qwen2.5-1.5B-Instruct", show_default=True,
              envvar="DEFENSE_LLM_MODEL_NAME")
@_DB_OPTION
@_INDEX_OPTION
@_LOG_OPTION
def eval_cmd(
    samples_path: str,
    output_path: str,
    mock: bool,
    model_id: str,
    db_path: str,
    index_path: str,
    log_path: str,
):
    """QA 샘플을 실행하고 정확도 리포트를 생성합니다.

    \b
    예시:
      defense-llm eval --samples tests/fixtures/dummy_qa_samples.json --mock
    """
    from defense_llm.knowledge.db_schema import init_db
    from defense_llm.rag.indexer import DocumentIndex
    from defense_llm.agent.planner_rules import classify_query, build_plan
    from defense_llm.agent.executor import Executor
    from defense_llm.audit.logger import AuditLogger
    from defense_llm.eval.runner import EvalRunner
    from defense_llm.serving.mock_llm import MockLLMAdapter

    _ensure_parent_dir(db_path)
    init_db(db_path)

    with open(samples_path, encoding="utf-8") as f:
        if samples_path.endswith(".yaml") or samples_path.endswith(".yml"):
            import yaml
            samples = yaml.safe_load(f)
        else:
            samples = json.load(f)

    idx = DocumentIndex.load(index_path) if (
        os.path.isdir(index_path) and os.path.isfile(os.path.join(index_path, "meta.json"))
    ) else DocumentIndex()

    if mock:
        llm = MockLLMAdapter()
        model_version = "mock-llm-0.0"
    else:
        from defense_llm.serving.qwen_adapter import Qwen25Adapter
        click.echo(f"모델 로딩 중: {model_id} …")
        llm = Qwen25Adapter(model_id=model_id, preload=True)
        model_version = model_id

    audit = AuditLogger(db_path)
    executor = Executor(
        llm_adapter=llm, index=idx, db_path=db_path, audit_logger=audit,
        model_version=model_version, index_version=_index_version(index_path),
        index_path=index_path,
    )

    _LEVEL = ["PUBLIC", "INTERNAL", "RESTRICTED", "SECRET"]

    def system_fn(question: str, user_context: dict) -> dict:
        label_filter = _LEVEL[: _LEVEL.index(user_context["clearance"]) + 1]
        qt = classify_query(question, user_context)
        plan = build_plan(qt, {"query": question, "security_label_filter": label_filter})
        return executor.execute(plan, user_context)

    runner = EvalRunner(system_fn=system_fn)

    click.echo(f"평가 실행 중 ({len(samples)}개 샘플)…")
    report = runner.run(samples)
    runner.save_report(report, output_path)

    click.echo()
    _print_separator()
    click.secho("평가 결과:", bold=True)
    click.echo(f"  전체: {report['total']}  통과: {report['passed']}  실패: {report['failed']}")
    color = "green" if report["pass_rate"] >= 0.7 else "yellow" if report["pass_rate"] >= 0.5 else "red"
    click.secho(f"  통과율: {report['pass_rate'] * 100:.1f}%", fg=color, bold=True)
    click.echo()
    for r in report["results"]:
        icon = click.style("✓", fg="green") if r["pass"] else click.style("✗", fg="red")
        cite = click.style("인용OK", fg="green") if r["citation_match"] else click.style("인용없음", fg="yellow")
        click.echo(f"  {icon} [{r['id']}] {cite}  {r.get('details', '')}")
    _print_separator()
    click.echo(f"\n  리포트 저장: {output_path}")


# ---------------------------------------------------------------------------
# config check
# ---------------------------------------------------------------------------

@cli.group("config")
def config_group():
    """설정 검증 명령"""


@config_group.command("check")
@click.option("--model-name", default="Qwen/Qwen2.5-1.5B-Instruct",
              envvar="DEFENSE_LLM_MODEL_NAME", show_default=True)
@_DB_OPTION
@_INDEX_OPTION
@_LOG_OPTION
@click.option("--security-level", default="INTERNAL", show_default=True,
              type=click.Choice(["PUBLIC", "INTERNAL", "RESTRICTED", "SECRET"]))
def config_check(model_name: str, db_path: str, index_path: str, log_path: str, security_level: str):
    """현재 설정값을 검증하고 출력합니다."""
    from defense_llm.config.settings import load_config

    cfg_dict = {
        "model_name": model_name,
        "db_path": db_path,
        "index_path": index_path,
        "log_path": log_path,
        "security_level": security_level,
    }

    click.echo("설정 검증 중…")
    try:
        cfg = load_config(cfg_dict, env_override=True)
        click.secho("✓ 설정이 유효합니다", fg="green")
        click.echo()
        _print_config_table(cfg)
    except ValueError as e:
        click.secho(f"✗ 설정 오류: {e}", fg="red", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)


def _index_version(index_path: str) -> str:
    """Return index version string based on meta.json mtime, or default."""
    meta = os.path.join(index_path, "meta.json")
    if os.path.isfile(meta):
        from datetime import datetime
        mtime = os.path.getmtime(meta)
        return "idx-" + datetime.fromtimestamp(mtime).strftime("%Y%m%d-%H%M")
    return "idx-00000000-0000"


def _print_separator(width: int = 60) -> None:
    click.echo("─" * width)


def _print_config_table(cfg) -> None:
    rows = [
        ("model_name",       cfg.model_name),
        ("db_path",          cfg.db_path),
        ("index_path",       cfg.index_path),
        ("log_path",         cfg.log_path),
        ("security_level",   cfg.security_level),
        ("chunk_max_tokens", cfg.chunk_max_tokens),
        ("top_k",            cfg.top_k),
    ]
    for key, val in rows:
        click.echo(f"  {key:<20} {val}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    cli()


if __name__ == "__main__":
    main()
