import logging


def configure_logging(level: str) -> None:
    logger = logging.getLogger("multilingual_rag_lab")
    logger.setLevel(level.upper())
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s %(message)s request_id=%(request_id)s",
                defaults={"request_id": "-"},
            )
        )
        logger.addHandler(handler)
    logger.propagate = False
