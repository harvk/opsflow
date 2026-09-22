from __future__ import annotations

import argparse
import json
import os
from dataclasses import (
    dataclass,
)
from time import (
    sleep,
)

from sqlalchemy.exc import (
    SQLAlchemyError,
)

from app.db.session import (
    SessionLocal,
)
from app.messaging.sqs_incident_task_completion_publisher import (
    SqsIncidentTaskCompletionPublisher,
)
from app.repositories.sqlalchemy_incident_task_completion_outbox_repository import (
    SqlAlchemyIncidentTaskCompletionOutboxRepository,
)
from app.services.incident_task_completion_outbox_relay_service import (
    CompletionOutboxRelayResult,
    IncidentTaskCompletionOutboxRelayService,
)

DEFAULT_POLL_SECONDS = (
    2.0
)

DEFAULT_RETRY_SECONDS = (
    15
)


@dataclass(
    frozen=True,
    slots=True,
)
class CompletionOutboxRelaySettings:
    realtime_notification_queue_url: str

    poll_seconds: float

    retry_seconds: int


def _log(
    event: str,
    **fields: object,
) -> None:
    print(
        json.dumps(
            {
                "event": event,
                **fields,
            },
            sort_keys=True,
            default=str,
        ),
        flush=True,
    )


def _required_environment(
    name: str,
) -> str:
    value = os.getenv(
        name,
        "",
    ).strip()

    if not value:
        raise RuntimeError(
            f"{name} must be configured."
        )

    return value


def _positive_float_environment(
    name: str,
    default: float,
) -> float:
    raw_value = os.getenv(
        name
    )

    if raw_value is None:
        return default

    try:
        value = float(
            raw_value
        )

    except ValueError as exc:
        raise RuntimeError(
            f"{name} must be numeric."
        ) from exc

    if value <= 0:
        raise RuntimeError(
            f"{name} must be greater than zero."
        )

    return value


def _positive_int_environment(
    name: str,
    default: int,
) -> int:
    raw_value = os.getenv(
        name
    )

    if raw_value is None:
        return default

    try:
        value = int(
            raw_value
        )

    except ValueError as exc:
        raise RuntimeError(
            f"{name} must be a whole number."
        ) from exc

    if value <= 0:
        raise RuntimeError(
            f"{name} must be greater than zero."
        )

    return value


def load_completion_outbox_relay_settings(
) -> CompletionOutboxRelaySettings:
    return (
        CompletionOutboxRelaySettings(
            realtime_notification_queue_url=(
                _required_environment(
                    "REALTIME_NOTIFICATION_QUEUE_URL"
                )
            ),
            poll_seconds=(
                _positive_float_environment(
                    "INCIDENT_TASK_COMPLETION_"
                    "OUTBOX_RELAY_POLL_SECONDS",
                    DEFAULT_POLL_SECONDS,
                )
            ),
            retry_seconds=(
                _positive_int_environment(
                    "INCIDENT_TASK_COMPLETION_"
                    "OUTBOX_RELAY_RETRY_SECONDS",
                    DEFAULT_RETRY_SECONDS,
                )
            ),
        )
    )


def _log_result(
    result: CompletionOutboxRelayResult,
) -> None:
    if (
        result.outcome
        == "no_pending_event"
    ):
        _log(
            (
                "incident_task_completion_"
                "outbox_relay_idle"
            ),
            level="debug",
        )

        return

    if (
        result.outcome
        == "published"
    ):
        _log(
            (
                "incident_task_completion_"
                "event_published"
            ),
            level="info",
            event_id=(
                result.event_id
            ),
            task_id=(
                result.task_id
            ),
            incident_id=(
                result.incident_id
            ),
            correlation_id=(
                result.correlation_id
            ),
            sqs_message_id=(
                result
                .sqs_message_id
            ),
            publish_attempt=(
                result
                .publish_attempt
            ),
        )

        return

    _log(
        (
            "incident_task_completion_"
            "publication_failed"
        ),
        level="error",
        event_id=(
            result.event_id
        ),
        task_id=(
            result.task_id
        ),
        incident_id=(
            result.incident_id
        ),
        correlation_id=(
            result.correlation_id
        ),
        publish_attempt=(
            result.publish_attempt
        ),
        error=(
            result.error
        ),
    )


def relay_one(
    settings: CompletionOutboxRelaySettings,
) -> CompletionOutboxRelayResult:
    session = (
        SessionLocal()
    )

    try:
        repository = (
            SqlAlchemyIncidentTaskCompletionOutboxRepository(
                session
            )
        )

        publisher = (
            SqsIncidentTaskCompletionPublisher(
                queue_url=(
                    settings
                    .realtime_notification_queue_url
                )
            )
        )

        service = (
            IncidentTaskCompletionOutboxRelayService(
                repository=(
                    repository
                ),
                publisher=(
                    publisher
                ),
                retry_seconds=(
                    settings
                    .retry_seconds
                ),
            )
        )

        result = (
            service.relay_once()
        )

        session.commit()

        return result

    except SQLAlchemyError:
        session.rollback()

        raise

    finally:
        session.close()


def main(
) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Publish OpsFlow Incident task-completion "
            "outbox events to the realtime notification "
            "Amazon SQS queue."
        )
    )

    parser.add_argument(
        "--once",
        action="store_true",
        help=(
            "Attempt one eligible completion-event outbox "
            "publication and exit."
        ),
    )

    args = parser.parse_args()

    settings = (
        load_completion_outbox_relay_settings()
    )

    _log(
        (
            "incident_task_completion_"
            "outbox_relay_started"
        ),
        level="info",
        poll_seconds=(
            settings.poll_seconds
        ),
        retry_seconds=(
            settings.retry_seconds
        ),
        run_once=(
            args.once
        ),
    )

    while True:
        result = relay_one(
            settings
        )

        _log_result(
            result
        )

        if args.once:
            return

        sleep(
            settings.poll_seconds
        )


if __name__ == "__main__":
    main()
