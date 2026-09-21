from __future__ import annotations

import argparse
import json
import os
from collections.abc import Callable
from dataclasses import (
    dataclass,
)
from time import (
    monotonic,
    sleep,
)
from typing import (
    Literal,
)
from uuid import (
    UUID,
)

from botocore.exceptions import (
    BotoCoreError,
    ClientError,
)
from sqlalchemy.exc import (
    SQLAlchemyError,
)

from app.db.session import (
    SessionLocal,
)
from app.domain.incident_task_execution import (
    IncidentTaskExecution,
)
from app.repositories.dynamodb_incident_task_execution_repository import (
    DynamoDbIncidentTaskExecutionRepository,
    ExecutionStateOwnershipLostError,
)
from app.repositories.incident_task_execution_repository import (
    IncidentTaskExecutionRepository,
)
from app.repositories.sqlalchemy_incident_repository import (
    SqlAlchemyIncidentRepository,
)
from app.services.exceptions import (
    IncidentNotFoundError,
)
from app.services.incident_task_processing_service import (
    IncidentProcessingResult,
    IncidentTaskProcessingService,
)

DEFAULT_STATUS_INDEX_NAME = (
    "status-created-at-index"
)

DEFAULT_POLL_SECONDS = (
    5.0
)

DEFAULT_BATCH_SIZE = (
    10
)

DEFAULT_LEASE_SECONDS = (
    60
)


class RetryableIncidentTaskProcessingError(
    RuntimeError
):
    """
    Raised when PostgreSQL processing fails for a condition
    that should be retried rather than permanently failed.
    """


@dataclass(
    frozen=True,
    slots=True,
)
class ReconcilerSettings:
    task_execution_table_name: str

    status_index_name: str

    poll_seconds: float

    batch_size: int

    lease_seconds: int


@dataclass(
    frozen=True,
    slots=True,
)
class ReconciliationSummary:
    discovered: int

    claimed: int

    succeeded: int

    retryable_failures: int

    permanent_failures: int

    skipped: int


ReconciliationOutcome = Literal[
    "succeeded",
    "retryable_failure",
    "permanent_failure",
]


IncidentProcessor = Callable[
    [UUID],
    IncidentProcessingResult,
]


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


def load_reconciler_settings(
) -> ReconcilerSettings:
    return (
        ReconcilerSettings(
            task_execution_table_name=(
                _required_environment(
                    "TASK_EXECUTION_TABLE_NAME"
                )
            ),
            status_index_name=(
                os.getenv(
                    "TASK_EXECUTION_STATUS_INDEX_NAME",
                    DEFAULT_STATUS_INDEX_NAME,
                )
                .strip()
                or DEFAULT_STATUS_INDEX_NAME
            ),
            poll_seconds=(
                _positive_float_environment(
                    "INCIDENT_TASK_RECONCILER_"
                    "POLL_SECONDS",
                    DEFAULT_POLL_SECONDS,
                )
            ),
            batch_size=(
                _positive_int_environment(
                    "INCIDENT_TASK_RECONCILER_"
                    "BATCH_SIZE",
                    DEFAULT_BATCH_SIZE,
                )
            ),
            lease_seconds=(
                _positive_int_environment(
                    "INCIDENT_TASK_RECONCILER_"
                    "LEASE_SECONDS",
                    DEFAULT_LEASE_SECONDS,
                )
            ),
        )
    )


def process_incident_with_postgres(
    incident_id: UUID,
) -> IncidentProcessingResult:
    """
    Execute one Incident business operation inside one
    PostgreSQL transaction.

    Missing Incidents remain permanent domain failures.

    SQLAlchemy/database failures are wrapped in a dedicated
    retryable exception so the reconciliation loop does not
    blindly catch programming errors.
    """

    session = (
        SessionLocal()
    )

    try:
        repository = (
            SqlAlchemyIncidentRepository(
                session
            )
        )

        service = (
            IncidentTaskProcessingService(
                repository
            )
        )

        result = (
            service.process(
                incident_id
            )
        )

        session.commit()

        return result

    except IncidentNotFoundError:
        session.rollback()

        raise

    except SQLAlchemyError as exc:
        session.rollback()

        raise (
            RetryableIncidentTaskProcessingError(
                "PostgreSQL Incident task processing "
                "failed."
            )
        ) from exc

    finally:
        session.close()


class IncidentTaskReconciler:
    def __init__(
        self,
        *,
        execution_repository: (
            IncidentTaskExecutionRepository
        ),
        processor: IncidentProcessor,
        batch_size: int,
        lease_seconds: int,
    ) -> None:
        self._execution_repository = (
            execution_repository
        )

        self._processor = (
            processor
        )

        self._batch_size = (
            batch_size
        )

        self._lease_seconds = (
            lease_seconds
        )

    def reconcile_once(
        self,
    ) -> ReconciliationSummary:
        candidates = (
            self
            ._execution_repository
            .list_reconcilable(
                limit=(
                    self._batch_size
                )
            )
        )

        claimed_count = 0
        succeeded_count = 0
        retryable_failure_count = 0
        permanent_failure_count = 0
        skipped_count = 0

        for candidate in candidates:
            claimed = (
                self
                ._execution_repository
                .claim(
                    candidate,
                    lease_seconds=(
                        self
                        ._lease_seconds
                    ),
                )
            )

            if claimed is None:
                skipped_count += 1

                continue

            claimed_count += 1

            outcome = (
                self._reconcile_claimed(
                    claimed
                )
            )

            if outcome == "succeeded":
                succeeded_count += 1

            elif (
                outcome
                == "retryable_failure"
            ):
                retryable_failure_count += 1

            elif (
                outcome
                == "permanent_failure"
            ):
                permanent_failure_count += 1

        return (
            ReconciliationSummary(
                discovered=len(
                    candidates
                ),
                claimed=(
                    claimed_count
                ),
                succeeded=(
                    succeeded_count
                ),
                retryable_failures=(
                    retryable_failure_count
                ),
                permanent_failures=(
                    permanent_failure_count
                ),
                skipped=(
                    skipped_count
                ),
            )
        )

    def _reconcile_claimed(
        self,
        execution: IncidentTaskExecution,
    ) -> ReconciliationOutcome:
        started = monotonic()

        try:
            result = (
                self._processor(
                    execution.incident_id
                )
            )

        except IncidentNotFoundError as exc:
            self._safe_mark_failed(
                execution,
                error=str(
                    exc
                ),
            )

            _log(
                "incident_task_reconciliation_failed",
                level="error",
                failure_type="permanent",
                task_id=(
                    execution.task_id
                ),
                incident_id=(
                    execution.incident_id
                ),
                correlation_id=(
                    execution
                    .correlation_id
                ),
                reconciliation_attempt=(
                    execution
                    .reconciliation_attempts
                ),
                duration_ms=int(
                    (
                        monotonic()
                        - started
                    )
                    * 1000
                ),
                error=str(
                    exc
                ),
            )

            return (
                "permanent_failure"
            )

        except (
            RetryableIncidentTaskProcessingError
        ) as exc:
            self._safe_mark_retryable(
                execution,
                error=str(
                    exc
                ),
            )

            _log(
                "incident_task_reconciliation_failed",
                level="error",
                failure_type="retryable",
                task_id=(
                    execution.task_id
                ),
                incident_id=(
                    execution.incident_id
                ),
                correlation_id=(
                    execution
                    .correlation_id
                ),
                reconciliation_attempt=(
                    execution
                    .reconciliation_attempts
                ),
                duration_ms=int(
                    (
                        monotonic()
                        - started
                    )
                    * 1000
                ),
                error=str(
                    exc
                ),
            )

            return (
                "retryable_failure"
            )

        try:
            (
                self
                ._execution_repository
                .mark_succeeded(
                    execution,
                    result={
                        "incident_id": str(
                            result.incident_id
                        ),
                        "incident_status": (
                            result
                            .status
                            .value
                        ),
                        "business_changed": (
                            result.changed
                        ),
                        "acknowledged_at": (
                            result
                            .acknowledged_at
                            .isoformat()
                            if (
                                result
                                .acknowledged_at
                                is not None
                            )
                            else ""
                        ),
                    },
                )
            )

        except (
            ExecutionStateOwnershipLostError
        ) as exc:
            _log(
                "incident_task_execution_ownership_lost",
                level="warning",
                task_id=(
                    execution.task_id
                ),
                incident_id=(
                    execution.incident_id
                ),
                correlation_id=(
                    execution
                    .correlation_id
                ),
                error=str(
                    exc
                ),
            )

            return (
                "retryable_failure"
            )

        except (
            BotoCoreError,
            ClientError,
        ) as exc:
            _log(
                "incident_task_execution_state_"
                "completion_failed",
                level="error",
                task_id=(
                    execution.task_id
                ),
                incident_id=(
                    execution.incident_id
                ),
                correlation_id=(
                    execution
                    .correlation_id
                ),
                error=str(
                    exc
                ),
            )

            return (
                "retryable_failure"
            )

        _log(
            "incident_task_reconciled",
            level="info",
            task_id=(
                execution.task_id
            ),
            incident_id=(
                execution.incident_id
            ),
            correlation_id=(
                execution
                .correlation_id
            ),
            reconciliation_attempt=(
                execution
                .reconciliation_attempts
            ),
            incident_status=(
                result.status.value
            ),
            business_changed=(
                result.changed
            ),
            duration_ms=int(
                (
                    monotonic()
                    - started
                )
                * 1000
            ),
        )

        return (
            "succeeded"
        )

    def _safe_mark_retryable(
        self,
        execution: IncidentTaskExecution,
        *,
        error: str,
    ) -> None:
        try:
            (
                self
                ._execution_repository
                .mark_retryable_failure(
                    execution,
                    error=error,
                )
            )

        except (
            ExecutionStateOwnershipLostError
        ) as exc:
            _log(
                "incident_task_execution_ownership_lost",
                level="warning",
                task_id=(
                    execution.task_id
                ),
                error=str(
                    exc
                ),
            )

        except (
            BotoCoreError,
            ClientError,
        ) as exc:
            _log(
                "incident_task_execution_state_"
                "retry_reset_failed",
                level="error",
                task_id=(
                    execution.task_id
                ),
                error=str(
                    exc
                ),
            )

    def _safe_mark_failed(
        self,
        execution: IncidentTaskExecution,
        *,
        error: str,
    ) -> None:
        try:
            (
                self
                ._execution_repository
                .mark_failed(
                    execution,
                    error=error,
                )
            )

        except (
            ExecutionStateOwnershipLostError
        ) as exc:
            _log(
                "incident_task_execution_ownership_lost",
                level="warning",
                task_id=(
                    execution.task_id
                ),
                error=str(
                    exc
                ),
            )

        except (
            BotoCoreError,
            ClientError,
        ) as exc:
            _log(
                "incident_task_execution_state_"
                "failure_mark_failed",
                level="error",
                task_id=(
                    execution.task_id
                ),
                error=str(
                    exc
                ),
            )


def build_reconciler(
    settings: ReconcilerSettings,
) -> IncidentTaskReconciler:
    repository = (
        DynamoDbIncidentTaskExecutionRepository(
            table_name=(
                settings
                .task_execution_table_name
            ),
            status_index_name=(
                settings
                .status_index_name
            ),
        )
    )

    return (
        IncidentTaskReconciler(
            execution_repository=(
                repository
            ),
            processor=(
                process_incident_with_postgres
            ),
            batch_size=(
                settings.batch_size
            ),
            lease_seconds=(
                settings.lease_seconds
            ),
        )
    )


def main(
) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Reconcile AWS Incident task execution state "
            "into OpsFlow PostgreSQL business state."
        )
    )

    parser.add_argument(
        "--once",
        action="store_true",
        help=(
            "Run one reconciliation cycle and exit."
        ),
    )

    args = (
        parser.parse_args()
    )

    settings = (
        load_reconciler_settings()
    )

    reconciler = (
        build_reconciler(
            settings
        )
    )

    _log(
        "incident_task_reconciler_started",
        level="info",
        table_name=(
            settings
            .task_execution_table_name
        ),
        status_index_name=(
            settings
            .status_index_name
        ),
        batch_size=(
            settings.batch_size
        ),
        lease_seconds=(
            settings.lease_seconds
        ),
        poll_seconds=(
            settings.poll_seconds
        ),
        run_once=(
            args.once
        ),
    )

    while True:
        summary = (
            reconciler
            .reconcile_once()
        )

        _log(
            "incident_task_reconciliation_cycle",
            level="info",
            discovered=(
                summary.discovered
            ),
            claimed=(
                summary.claimed
            ),
            succeeded=(
                summary.succeeded
            ),
            retryable_failures=(
                summary
                .retryable_failures
            ),
            permanent_failures=(
                summary
                .permanent_failures
            ),
            skipped=(
                summary.skipped
            ),
        )

        if args.once:
            return

        sleep(
            settings.poll_seconds
        )


if __name__ == "__main__":
    main()
