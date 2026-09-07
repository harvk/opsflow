from __future__ import annotations

import logging
import sys


SECURITY_LOGGER_NAME = (
    "opsflow.security"
)


def configure_security_logging(
) -> None:
    """
    Configure the dedicated security-event logger.

    Containers capture stderr/stdout, which gives us a clean
    migration path to AWS CloudWatch Logs later.

    We deliberately emit only the message itself because the
    SecurityEventLogger already produces JSON containing its
    own timestamp, severity, event ID, and metadata.
    """

    logger = logging.getLogger(
        SECURITY_LOGGER_NAME
    )

    logger.setLevel(
        logging.INFO
    )

    # Prevent duplicate handlers if create_app() is called
    # repeatedly during tests.
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

    # We own the output for this dedicated logger.
    logger.propagate = False