class ApplicationError(Exception):
    """Base error whose message is safe to expose to API clients."""


class DocumentNotFound(ApplicationError):
    pass


class UnsupportedDocument(ApplicationError):
    pass


class IngestionFailed(ApplicationError):
    pass


class IndexIncompatible(ApplicationError):
    pass


class IndexNotReady(ApplicationError):
    pass


class DependencyUnavailable(ApplicationError):
    pass


class LLMProviderError(ApplicationError):
    pass
