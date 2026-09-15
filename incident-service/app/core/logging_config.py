from __future__ import annotations

import logging
import sys

REQUEST_LOGGER_NAME = (
    "opsflow.http"
)


def configure_request_logging(
) -> None:
    """
    Configure the Incident Service HTTP request logger.

    Request events are serialized by application code, so the
    logging handler emits only the JSON message.
    """

    logger = logging.getLogger(
        REQUEST_LOGGER_NAME
    )

    logger.setLevel(
        logging.INFO
    )

    # create_app() is called repeatedly during tests. Avoid
    # attaching another handler on every construction.
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

    logger.propagate = False