from typing import Any

from multilingual_rag_lab.domain.index_manifest import IndexManifest
from multilingual_rag_lab.domain.models import IndexSpec


def preflight(
    store: Any, manifest: IndexManifest, spec: IndexSpec, document_ids: dict[str, str]
) -> dict[str, int]:
    if manifest.spec != spec:
        raise ValueError("Manifest IndexSpec differs from evaluation configuration")
    store.select_active(spec, manifest.collection_name)
    counts: dict[str, int] = store.validate_contents(
        spec, manifest.collection_name, set(document_ids)
    )
    # Freeze the physical collection, not an alias resolved for each query.
    store.collection_name = manifest.collection_name
    return counts
