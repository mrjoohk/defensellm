import sys
sys.path.append('src')

def search_test():
    from defense_llm.agent.executor import Executor
    from defense_llm.rag.indexer import DocumentIndex
    from defense_llm.rag.embedder import Qwen25Embedder

    embedder = Qwen25Embedder()
    
    index_path = "/home/rtv-24n10/defenseLLM_claude/data/index"
    index = DocumentIndex.load(index_path, embedder)

    print("Index size:", len(index._meta))
    stanag_chunks = [v for k, v in index._meta.items() if "STANAG" in v.get("doc_id", "")]
    print(f"Chunks containing STANAG in doc_id: {len(stanag_chunks)}")
    
    if len(stanag_chunks) > 0:
        c = stanag_chunks[0]
        print(f"First chunk:\ndoc_id: {c['doc_id']}\ntext: {c['text'][:200]}")

if __name__ == "__main__":
    search_test()
