import sys

from loguru import logger


def configure_logger(*, debug: bool) -> None:
    """Configure logger for use in processes and threads."""
    logger.remove()
    _ = logger.add(
        sys.stderr,
        level="DEBUG" if debug else "WARNING",
    )
