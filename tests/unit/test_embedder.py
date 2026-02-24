"""Unit tests for rag/embedder.py — TFIDFEmbedder + interface contract."""

import numpy as np
import pytest

from defense_llm.rag.embedder import TFIDFEmbedder, AbstractEmbedder


class TestTFIDFEmbedder:
    """Tests that run without any model download (offline)."""

    def test_implements_abstract_interface(self):
        emb = TFIDFEmbedder()
        assert isinstance(emb, AbstractEmbedder)

    def test_encode_returns_2d_float32(self):
        emb = TFIDFEmbedder(vocab_size=128)
        vecs = emb.encode(["항공기 운용", "미사일 무장"])
        assert vecs.ndim == 2
        assert vecs.dtype == np.float32
        assert vecs.shape[0] == 2
        assert vecs.shape[1] == 128

    def test_dim_property(self):
        emb = TFIDFEmbedder(vocab_size=64)
        emb.fit(["테스트 문서"])
        assert emb.dim == 64

    def test_l2_normalised_rows(self):
        emb = TFIDFEmbedder(vocab_size=128)
        vecs = emb.encode(["항공기", "전투기 무장 운용"])
        norms = np.linalg.norm(vecs, axis=1)
        # All non-zero rows should have norm ≈ 1.0
        for n in norms:
            if n > 0:
                assert abs(n - 1.0) < 1e-5, f"Row norm {n} not normalised"

    def test_encode_auto_fits_on_first_call(self):
        emb = TFIDFEmbedder(vocab_size=64)
        # No explicit fit() — should still work
        vecs = emb.encode(["자동 피팅 테스트"])
        assert vecs.shape[0] == 1

    def test_fit_then_encode(self):
        corpus = ["항공기 운용 절차", "무장 탑재 한계", "정비 주기 기준"]
        emb = TFIDFEmbedder(vocab_size=128)
        emb.fit(corpus)
        vecs = emb.encode(corpus)
        assert vecs.shape == (3, 128)

    def test_same_text_same_vector(self):
        emb = TFIDFEmbedder(vocab_size=64)
        emb.fit(["동일 텍스트 반복 테스트"])
        v1 = emb.encode(["동일 텍스트 반복 테스트"])
        v2 = emb.encode(["동일 텍스트 반복 테스트"])
        np.testing.assert_array_almost_equal(v1, v2)

    def test_cosine_similarity_via_dot(self):
        """Two identical texts → cosine sim 1.0; orthogonal texts → ~0."""
        emb = TFIDFEmbedder(vocab_size=256)
        texts = ["항공기 운용", "완전히 다른 내용 xyz"]
        emb.fit(texts)
        vecs = emb.encode(texts)
        # Same text similarity
        same_sim = float(np.dot(vecs[0], vecs[0]))
        assert abs(same_sim - 1.0) < 1e-4


class TestDocumentIndexWithTFIDFEmbedder:
    """DocumentIndex with injected TFIDFEmbedder (real dense path)."""

    def _build_index(self):
        from defense_llm.rag.chunker import chunk_document
        from defense_llm.rag.indexer import DocumentIndex

        emb = TFIDFEmbedder(vocab_size=256)
        text = "KF-21 항공기 최대 순항 고도는 15000m입니다.\n\n정비 주기는 100 비행 시간입니다."
        result = chunk_document("DOC-001", "v1.0", text, doc_field="air")
        # Fit embedder on corpus first
        emb.fit([c.text for c in result["chunks"]])
        idx = DocumentIndex(embedder=emb)
        idx.add_chunks(result["chunks"])
        return idx

    def test_dense_path_returns_results(self):
        idx = self._build_index()
        results = idx.search("항공기 고도", top_k=3)
        assert len(results) >= 1

    def test_each_result_has_score(self):
        idx = self._build_index()
        results = idx.search("정비", top_k=2)
        for r in results:
            assert "score" in r
            assert isinstance(r["score"], float)


class TestDocumentIndexPersistence:
    """save() / load() roundtrip for DocumentIndex (P0 — index persistence)."""

    def test_save_and_load_roundtrip(self, tmp_path):
        from defense_llm.rag.chunker import chunk_document
        from defense_llm.rag.indexer import DocumentIndex

        emb = TFIDFEmbedder(vocab_size=128)
        text = "전투기 무장 탑재 한계는 7000kg입니다.\n\n비상 절차 참고 바랍니다."
        result = chunk_document("DOC-SAVE", "v1.0", text, doc_field="weapon")
        emb.fit([c.text for c in result["chunks"]])

        idx = DocumentIndex(embedder=emb)
        idx.add_chunks(result["chunks"])
        count_before = idx.chunk_count()

        # Save
        index_dir = str(tmp_path / "idx")
        idx.save(index_dir)

        # Load
        idx2 = DocumentIndex.load(index_dir, embedder=emb)
        assert idx2.chunk_count() == count_before

    def test_loaded_index_is_searchable(self, tmp_path):
        from defense_llm.rag.chunker import chunk_document
        from defense_llm.rag.indexer import DocumentIndex

        emb = TFIDFEmbedder(vocab_size=128)
        text = "레이더 시스템 운용 교범 내용입니다."
        result = chunk_document("DOC-LOAD", "v1.0", text, doc_field="sensor")
        emb.fit([c.text for c in result["chunks"]])

        idx = DocumentIndex(embedder=emb)
        idx.add_chunks(result["chunks"])
        idx.save(str(tmp_path / "idx"))

        idx2 = DocumentIndex.load(str(tmp_path / "idx"), embedder=emb)
        results = idx2.search("레이더", top_k=3)
        assert len(results) >= 1

    def test_load_missing_dir_raises(self, tmp_path):
        from defense_llm.rag.indexer import DocumentIndex
        with pytest.raises(FileNotFoundError):
            DocumentIndex.load(str(tmp_path / "nonexistent"))

    def test_save_creates_expected_files(self, tmp_path):
        from defense_llm.rag.chunker import chunk_document
        from defense_llm.rag.indexer import DocumentIndex
        import os

        emb = TFIDFEmbedder(vocab_size=64)
        text = "테스트 저장 파일 확인"
        result = chunk_document("DOC-FILES", "v1.0", text, doc_field="air")
        emb.fit([c.text for c in result["chunks"]])
        idx = DocumentIndex(embedder=emb)
        idx.add_chunks(result["chunks"])

        index_dir = str(tmp_path / "idx_files")
        idx.save(index_dir)

        for fname in ["bm25.pkl", "dense.pkl", "legacy.pkl", "meta.json"]:
            assert os.path.isfile(os.path.join(index_dir, fname)), f"Missing: {fname}"
