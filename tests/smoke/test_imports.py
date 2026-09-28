def test_imports_do_not_load_heavy_models() -> None:
    from multilingual_rag_lab.adapters.outbound.chunking import HybridChunkerAdapter
    from multilingual_rag_lab.adapters.outbound.embeddings import QwenEmbedder

    assert QwenEmbedder("model", "cpu", 1)._model is None
    assert HybridChunkerAdapter("model")._chunker is None


def test_imports_in_clean_process_have_no_heavy_side_effects():
    import subprocess
    import sys

    subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            "import sys; import multilingual_rag_lab.adapters.inbound.api.app; import multilingual_rag_lab.adapters.inbound.cli.main; assert not {'torch','sentence_transformers','docling','fastembed'} & sys.modules.keys()",
        ],
        check=True,
    )
