from __future__ import annotations

from typing import (
    Any,
)
from uuid import (
    uuid4,
)

from botocore.exceptions import (
    ClientError,
)

from app.domain.incident_task_execution import (
    IncidentTaskExecution,
    IncidentTaskExecutionStatus,
)
from app.repositories.dynamodb_incident_task_execution_repository import (
    DynamoDbIncidentTaskExecutionRepository,
)


class RecordingTable:
    def __init__(
        self,
    ) -> None:
        self.query_responses: list[
            dict[str, Any]
        ] = []

        self.update_responses: list[
            dict[str, Any]
        ] = []

        self.update_error: (
            ClientError
            | None
        ) = None

        self.query_calls: list[
            dict[str, Any]
        ] = []

        self.update_calls: list[
            dict[str, Any]
        ] = []

    def query(
        self,
        **kwargs: Any,
    ) -> dict[str, Any]:
        self.query_calls.append(
            kwargs
        )

        if not self.query_responses:
            return {
                "Items": [],
            }

        return (
            self.query_responses
            .pop(
                0
            )
        )

    def update_item(
        self,
        **kwargs: Any,
    ) -> dict[str, Any]:
        self.update_calls.append(
            kwargs
        )

        if self.update_error is not None:
            raise (
                self.update_error
            )

        if not self.update_responses:
            return {}

        return (
            self.update_responses
            .pop(
                0
            )
        )


def build_item(
    *,
    status: (
        IncidentTaskExecutionStatus
    ),
) -> dict[str, Any]:
    return {
        "task_id": str(
            uuid4()
        ),
        "incident_id": str(
            uuid4()
        ),
        "task_type": (
            "incident.processing.requested"
        ),
        "correlation_id": str(
            uuid4()
        ),
        "created_at": (
            "2026-09-21T12:00:00+00:00"
        ),
        "status": (
            status.value
        ),
        "reconciliation_attempts": 0,
    }


def test_lists_ready_execution(
) -> None:
    table = RecordingTable()

    item = build_item(
        status=(
            IncidentTaskExecutionStatus
            .READY_FOR_INCIDENT_SERVICE
        )
    )

    table.query_responses = [
        {
            "Items": [
                item
            ],
        },
    ]

    repository = (
        DynamoDbIncidentTaskExecutionRepository(
            table_name="test-table",
            status_index_name=(
                "status-created-at-index"
            ),
            table=table,
        )
    )

    executions = (
        repository
        .list_reconcilable(
            limit=1
        )
    )

    assert len(
        executions
    ) == 1

    assert (
        executions[
            0
        ]
        .task_id
        == item[
            "task_id"
        ]
    )


def test_claim_returns_processing_execution(
) -> None:
    table = RecordingTable()

    ready_item = build_item(
        status=(
            IncidentTaskExecutionStatus
            .READY_FOR_INCIDENT_SERVICE
        )
    )

    claimed_item = {
        **ready_item,
        "status": (
            IncidentTaskExecutionStatus
            .INCIDENT_SERVICE_PROCESSING
            .value
        ),
        "reconciliation_attempts": 1,
        "lease_expires_at": (
            9999999999
        ),
        "reconciliation_token": (
            "claim-token"
        ),
    }

    table.update_responses = [
        {
            "Attributes": (
                claimed_item
            ),
        },
    ]

    repository = (
        DynamoDbIncidentTaskExecutionRepository(
            table_name="test-table",
            status_index_name=(
                "status-created-at-index"
            ),
            table=table,
        )
    )

    execution = (
        IncidentTaskExecution(
            task_id=(
                ready_item[
                    "task_id"
                ]
            ),
            incident_id=(
                uuid4()
            ),
            task_type=(
                "incident.processing.requested"
            ),
            correlation_id=(
                ready_item[
                    "correlation_id"
                ]
            ),
            created_at=(
                ready_item[
                    "created_at"
                ]
            ),
            status=(
                IncidentTaskExecutionStatus
                .READY_FOR_INCIDENT_SERVICE
            ),
            reconciliation_attempts=0,
        )
    )

    claimed = repository.claim(
        execution,
        lease_seconds=60,
    )

    assert claimed is not None

    assert (
        claimed.status
        is (
            IncidentTaskExecutionStatus
            .INCIDENT_SERVICE_PROCESSING
        )
    )

    assert (
        claimed.reconciliation_token
        == "claim-token"
    )


def test_claim_conflict_is_skipped(
) -> None:
    table = RecordingTable()

    table.update_error = (
        ClientError(
            {
                "Error": {
                    "Code": (
                        "ConditionalCheckFailedException"
                    ),
                    "Message": (
                        "claim lost"
                    ),
                },
            },
            "UpdateItem",
        )
    )

    repository = (
        DynamoDbIncidentTaskExecutionRepository(
            table_name="test-table",
            status_index_name=(
                "status-created-at-index"
            ),
            table=table,
        )
    )

    execution = (
        IncidentTaskExecution(
            task_id=str(
                uuid4()
            ),
            incident_id=(
                uuid4()
            ),
            task_type=(
                "incident.processing.requested"
            ),
            correlation_id=str(
                uuid4()
            ),
            created_at=(
                "2026-09-21T12:00:00+00:00"
            ),
            status=(
                IncidentTaskExecutionStatus
                .READY_FOR_INCIDENT_SERVICE
            ),
            reconciliation_attempts=0,
        )
    )

    claimed = repository.claim(
        execution,
        lease_seconds=60,
    )

    assert claimed is None
