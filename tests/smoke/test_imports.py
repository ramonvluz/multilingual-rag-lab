def test_imports_do_not_load_heavy_models() -> None:
    from multilingual_rag_lab.adapters.outbound.chunking import HybridChunkerAdapter
    from multilingual_rag_lab.adapters.outbound.embeddings import QwenEmbedder

    assert QwenEmbedder("model", "cpu", 1)._model is None
    assert HybridChunkerAdapter("model")._chunker is None
