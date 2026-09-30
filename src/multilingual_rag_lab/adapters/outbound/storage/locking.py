from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from filelock import FileLock, Timeout

from multilingual_rag_lab.domain.errors import MutationBusy


@contextmanager
def mutation_lock(runtime: Path) -> Iterator[None]:
    """OS-backed local lock, released even on process exit; never unlink the lock inode."""
    runtime.mkdir(parents=True, exist_ok=True)
    try:
        with FileLock(runtime / ".mutation.lock", timeout=0):
            yield
    except Timeout as error:
        raise MutationBusy("Another mutation is running on this runtime; retry later") from error
