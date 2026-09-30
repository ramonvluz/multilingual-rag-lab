class ApplicationError(Exception):
    """Base error whose message is safe to expose to API clients."""


class DocumentNotFound(ApplicationError):
    pass


class DocumentCorrupt(ApplicationError):
    pass


class UnsupportedDocument(ApplicationError):
    pass


class IngestionFailed(ApplicationError):
    pass


class MutationBusy(IngestionFailed):
    """Another process holds the local runtime mutation lock."""


class IndexIncompatible(ApplicationError):
    pass


class IndexNotReady(ApplicationError):
    pass


class DependencyUnavailable(ApplicationError):
    pass


class LLMProviderError(ApplicationError):
    pass
