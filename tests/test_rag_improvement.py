import numpy as np
from defense_llm.rag.chunker import chunk_document
from defense_llm.rag.indexer import DocumentIndex
from defense_llm.rag.chunker import _make_chunk_id

class DummyEmbedder:
    def encode(self, texts):
        # Return random vectors of dimension 8
        return np.random.randn(len(texts), 8).astype(np.float32)

def test_heading_aware_chunking():
    text = """
# Main Title
Some intro.
## Section 1
Content 1.
### Subsection A
Details A.
"""
    res = chunk_document("doc1", "v1", text, doc_field="air")
    chunks = res["chunks"]
    
    # Intro chunk
    assert chunks[0].section_path == "Main Title", f"Got {chunks[0].section_path}"
    # Section 1 chunk
    assert chunks[1].section_path == "Main Title > Section 1", f"Got {chunks[1].section_path}"
    # Subsection chunk
    assert chunks[2].section_path == "Main Title > Section 1 > Subsection A", f"Got {chunks[2].section_path}"
    print("Heading aware chunking passed!")

def test_exact_dedup():
    text1 = "This is a test document."
    text2 = "  This   is a\ntest document.  "
    
    id1 = _make_chunk_id(text1)
    id2 = _make_chunk_id(text2)
    assert id1 == id2
    print("Exact dedup passed!")

def test_near_dedup():
    idx = DocumentIndex(embedder=DummyEmbedder())
    
    # Insert first chunk
    res1 = chunk_document("doc1", "v1", "First chunk", doc_field="air", doc_type="spec")
    idx.add_chunks(res1["chunks"])
    
    assert idx.chunk_count() == 1
    
    # We will spoof the embedder to return identical vectors for the next chunk
    class SpoofEmbedder:
        def encode(self, texts):
            return idx._dense._matrix[0:1] # Return the exact same vector as the first one (similarity=1.0)
            
    idx._embedder = SpoofEmbedder()
    res2 = chunk_document("doc2", "v1", "Second chunk but highly similar", doc_field="air", doc_type="spec")
    idx.add_chunks(res2["chunks"])
    
    # It should not have been added
    assert idx.chunk_count() == 1
    print("Near dedup passed!")

if __name__ == "__main__":
    test_heading_aware_chunking()
    test_exact_dedup()
    test_near_dedup()
