"""Unit tests for RAG module (UF-020, UF-021, UF-022)."""

import pytest

from defense_llm.rag.chunker import chunk_document, E_VALIDATION as CHUNK_VALIDATION
from defense_llm.rag.indexer import DocumentIndex
from defense_llm.rag.retriever import hybrid_search, E_VALIDATION as RETRIEVER_VALIDATION
from defense_llm.rag.citation import package_citations, E_VALIDATION as CITATION_VALIDATION


DUMMY_TEXT = """
이 문서는 KF-21 항공기의 운용 절차를 설명합니다.

KF-21 항공기는 최대 순항 고도 15,000m에서 운용 가능합니다.
최대 이륙 중량은 25,600kg이며, 내부 연료 탑재량은 6,000kg입니다.

[PAGE 2]

무장 탑재 가능 항목:
- 공대공 미사일 AAM-II 4발
- 공대지 미사일 AGM-III 2발
- 정밀 유도 폭탄 2발

정비 주기는 100 비행 시간마다 점검을 실시합니다.
"""


# ---------------------------------------------------------------------------
# UF-020: Chunking
# ---------------------------------------------------------------------------

class TestChunkDocument:
    def test_returns_at_least_one_chunk(self):
        result = chunk_document("DOC-001", "v1.0", DUMMY_TEXT)
        assert result["indexed_count"] >= 1
        assert len(result["chunks"]) >= 1

    def test_chunk_has_required_fields(self):
        result = chunk_document("DOC-001", "v1.0", DUMMY_TEXT)
        for chunk in result["chunks"]:
            assert chunk.doc_id == "DOC-001"
            assert chunk.doc_rev == "v1.0"
            assert chunk.page >= 1
            assert chunk.section_id.startswith("sec-")
            assert chunk.text

    def test_empty_text_raises_validation(self):
        with pytest.raises(ValueError, match=CHUNK_VALIDATION):
            chunk_document("DOC-001", "v1.0", "")

    def test_whitespace_only_text_raises_validation(self):
        with pytest.raises(ValueError, match=CHUNK_VALIDATION):
            chunk_document("DOC-001", "v1.0", "   \n  ")

    def test_max_tokens_respected(self):
        result = chunk_document("DOC-001", "v1.0", DUMMY_TEXT, max_tokens=10, overlap=2)
        for chunk in result["chunks"]:
            assert chunk.token_count <= 10

    def test_page_parsing(self):
        result = chunk_document("DOC-001", "v1.0", DUMMY_TEXT)
        pages = {c.page for c in result["chunks"]}
        assert 1 in pages
        assert 2 in pages  # [PAGE 2] marker in DUMMY_TEXT

    def test_security_label_assigned(self):
        result = chunk_document("DOC-001", "v1.0", DUMMY_TEXT, security_label="RESTRICTED")
        for chunk in result["chunks"]:
            assert chunk.security_label == "RESTRICTED"


# ---------------------------------------------------------------------------
# UF-021: Hybrid Search
# ---------------------------------------------------------------------------

def _build_index_with_dummy() -> DocumentIndex:
    index = DocumentIndex()
    result = chunk_document("DOC-001", "v1.0", DUMMY_TEXT, security_label="INTERNAL", doc_field="air")
    index.add_chunks(result["chunks"])
    return index


class TestHybridSearch:
    def test_returns_results_for_matching_query(self):
        index = _build_index_with_dummy()
        results = hybrid_search(index, "KF-21 최대 고도", top_k=3)
        assert len(results) <= 3

    def test_empty_query_raises(self):
        index = _build_index_with_dummy()
        with pytest.raises(ValueError, match=RETRIEVER_VALIDATION):
            hybrid_search(index, "")

    def test_whitespace_query_raises(self):
        index = _build_index_with_dummy()
        with pytest.raises(ValueError, match=RETRIEVER_VALIDATION):
            hybrid_search(index, "   ")

    def test_field_filter_limits_results(self):
        index = DocumentIndex()
        # Add air document
        air_chunks = chunk_document("DOC-AIR", "v1.0", "전투기 항공 운용", doc_field="air")
        # Add weapon document
        wpn_chunks = chunk_document("DOC-WPN", "v1.0", "미사일 무장 운용", doc_field="weapon")
        index.add_chunks(air_chunks["chunks"])
        index.add_chunks(wpn_chunks["chunks"])

        results = hybrid_search(index, "운용", field_filter=["air"])
        for r in results:
            assert r["doc_field"] == "air"

    def test_security_label_filter_excludes_higher_labels(self):
        index = DocumentIndex()
        pub_chunks = chunk_document("DOC-PUB", "v1.0", "공개 정보 항공", security_label="PUBLIC", doc_field="air")
        sec_chunks = chunk_document("DOC-SEC", "v1.0", "기밀 정보 항공", security_label="SECRET", doc_field="air")
        index.add_chunks(pub_chunks["chunks"])
        index.add_chunks(sec_chunks["chunks"])

        results = hybrid_search(index, "항공", security_label_filter=["PUBLIC"])
        for r in results:
            assert r["security_label"] == "PUBLIC"

    def test_top_k_respected(self):
        index = _build_index_with_dummy()
        results = hybrid_search(index, "항공기", top_k=2)
        assert len(results) <= 2


# ---------------------------------------------------------------------------
# UF-022: Citation Packaging
# ---------------------------------------------------------------------------

class TestPackageCitations:
    def test_required_fields_present(self):
        chunks = [
            {"chunk_id": "c1", "doc_id": "DOC-001", "doc_rev": "v1.0",
             "page": 1, "section_id": "sec-0001", "text": "테스트 내용입니다."}
        ]
        citations = package_citations(chunks)
        assert len(citations) == 1
        c = citations[0]
        assert "doc_id" in c
        assert "doc_rev" in c
        assert "page" in c
        assert "snippet_hash" in c

    def test_snippet_hash_is_sha256(self):
        import hashlib
        chunks = [
            {"chunk_id": "c1", "doc_id": "DOC-001", "doc_rev": "v1.0",
             "page": 1, "section_id": "sec-0001", "text": "테스트"}
        ]
        citations = package_citations(chunks)
        expected_hash = hashlib.sha256("테스트".encode("utf-8")).hexdigest()
        assert citations[0]["snippet_hash"] == expected_hash

    def test_duplicate_text_same_hash(self):
        chunk = {"chunk_id": "c1", "doc_id": "DOC-001", "doc_rev": "v1.0",
                 "page": 1, "section_id": "sec-0001", "text": "동일 텍스트"}
        c1 = package_citations([chunk])
        c2 = package_citations([chunk])
        assert c1[0]["snippet_hash"] == c2[0]["snippet_hash"]

    def test_missing_doc_id_raises(self):
        bad_chunks = [
            {"chunk_id": "c1", "doc_rev": "v1.0", "text": "내용"}
        ]
        with pytest.raises(ValueError, match=CITATION_VALIDATION):
            package_citations(bad_chunks)

    def test_multiple_chunks_produce_multiple_citations(self):
        chunks = [
            {"chunk_id": f"c{i}", "doc_id": "DOC-001", "doc_rev": "v1.0",
             "page": i, "section_id": f"sec-{i:04d}", "text": f"내용 {i}"}
            for i in range(3)
        ]
        citations = package_citations(chunks)
        assert len(citations) == 3
