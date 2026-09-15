from __future__ import annotations

import logging
import sys

SECURITY_LOGGER_NAME = (
    "opsflow.security"
)

REQUEST_LOGGER_NAME = (
    "opsflow.http"
)


def _configure_message_only_logger(
    logger_name: str,
) -> None:
    """
    Configure one OpsFlow JSON logger.

    Application code constructs the complete JSON message.
    The Python logging layer therefore emits only the message
    and does not prepend another timestamp or log-level label.
    """

    logger = logging.getLogger(
        logger_name
    )

    logger.setLevel(
        logging.INFO
    )

    # Application factories are called repeatedly during
    # tests. Reusing the existing handler prevents duplicate
    # copies of every event.
    if logger.handlers:
        return

    handler = logging.StreamHandler(
        sys.stderr
    )

    handler.setLevel(
        logging.INFO
    )

    handler.setFormatter(
        logging.Formatter(
            "%(message)s"
        )
    )

    logger.addHandler(
        handler
    )

    # OpsFlow owns output for its dedicated JSON loggers.
    # Propagating to the root logger could duplicate events.
    logger.propagate = False


def configure_security_logging(
) -> None:
    """
    Configure the dedicated security-event logger.

    The SecurityEventLogger already produces JSON containing
    its timestamp, severity, event ID, and metadata.
    """

    _configure_message_only_logger(
        SECURITY_LOGGER_NAME
    )


def configure_request_logging(
) -> None:
    """
    Configure the distributed HTTP request logger.

    Request events are emitted as one JSON object per line so
    Docker and a future CloudWatch integration can ingest them
    without parsing human-oriented prefixes.
    """

    _configure_message_only_logger(
        REQUEST_LOGGER_NAME
    )