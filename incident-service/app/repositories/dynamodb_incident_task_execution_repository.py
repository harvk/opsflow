from __future__ import annotations

from datetime import (
    UTC,
    datetime,
)
from time import (
    time,
)
from typing import (
    Any,
)
from uuid import (
    UUID,
    uuid4,
)

import boto3
from botocore.exceptions import (
    ClientError,
)

from app.domain.incident_task_execution import (
    IncidentTaskExecution,
    IncidentTaskExecutionStatus,
)
from app.repositories.incident_task_execution_repository import (
    IncidentTaskExecutionRepository,
)


class ExecutionStateOwnershipLostError(
    RuntimeError
):
    """
    Raised when a reconciler tries to finish a task after
    losing its conditional execution claim.
    """


class DynamoDbIncidentTaskExecutionRepository(
    IncidentTaskExecutionRepository
):
    """
    DynamoDB implementation of Incident task reconciliation
    state.

    The reconciliation token prevents a worker whose lease
    expired from overwriting the result of a newer claimant.
    """

    def __init__(
        self,
        *,
        table_name: str,
        status_index_name: str,
        table: Any | None = None,
    ) -> None:
        self._status_index_name = (
            status_index_name
        )

        if table is not None:
            self._table = (
                table
            )

        else:
            dynamodb: Any = (
                boto3.resource(
                    "dynamodb"
                )
            )

            self._table = (
                dynamodb.Table(
                    table_name
                )
            )

    def list_reconcilable(
        self,
        *,
        limit: int,
    ) -> list[
        IncidentTaskExecution
    ]:
        ready_items = (
            self._query_status(
                status=(
                    IncidentTaskExecutionStatus
                    .READY_FOR_INCIDENT_SERVICE
                ),
                limit=limit,
            )
        )

        remaining = (
            limit
            - len(
                ready_items
            )
        )

        processing_items: list[
            dict[str, Any]
        ] = []

        if remaining > 0:
            processing_items = (
                self._query_expired_processing(
                    limit=remaining,
                )
            )

        all_items = (
            ready_items
            + processing_items
        )

        all_items.sort(
            key=lambda item: str(
                item[
                    "created_at"
                ]
            )
        )

        return [
            self._to_domain(
                item
            )
            for item in all_items[
                :limit
            ]
        ]

    def claim(
        self,
        execution: IncidentTaskExecution,
        *,
        lease_seconds: int,
    ) -> (
        IncidentTaskExecution
        | None
    ):
        now_epoch = int(
            time()
        )

        now = (
            datetime.now(
                UTC
            )
            .isoformat()
        )

        lease_expires_at = (
            now_epoch
            + lease_seconds
        )

        reconciliation_token = str(
            uuid4()
        )

        try:
            response = (
                self._table.update_item(
                    Key={
                        "task_id": (
                            execution.task_id
                        ),
                    },
                    UpdateExpression=(
                        "SET "
                        "#status = :processing, "
                        "reconciliation_started_at = :now, "
                        "reconciliation_token = :token, "
                        "lease_expires_at = :lease, "
                        "updated_at = :now "
                        "ADD reconciliation_attempts :one"
                    ),
                    ConditionExpression=(
                        "#status = :ready "
                        "OR ("
                        "#status = :processing "
                        "AND lease_expires_at <= :now_epoch"
                        ")"
                    ),
                    ExpressionAttributeNames={
                        "#status": (
                            "status"
                        ),
                    },
                    ExpressionAttributeValues={
                        ":ready": (
                            IncidentTaskExecutionStatus
                            .READY_FOR_INCIDENT_SERVICE
                            .value
                        ),
                        ":processing": (
                            IncidentTaskExecutionStatus
                            .INCIDENT_SERVICE_PROCESSING
                            .value
                        ),
                        ":now": now,
                        ":now_epoch": (
                            now_epoch
                        ),
                        ":lease": (
                            lease_expires_at
                        ),
                        ":token": (
                            reconciliation_token
                        ),
                        ":one": 1,
                    },
                    ReturnValues=(
                        "ALL_NEW"
                    ),
                )
            )

        except ClientError as exc:
            if (
                self._error_code(
                    exc
                )
                == (
                    "ConditionalCheckFailedException"
                )
            ):
                return None

            raise

        attributes = (
            response.get(
                "Attributes"
            )
        )

        if not isinstance(
            attributes,
            dict,
        ):
            raise TypeError(
                "DynamoDB did not return claimed "
                "execution attributes as an object."
            )

        return self._to_domain(
            attributes
        )

    def mark_succeeded(
        self,
        execution: IncidentTaskExecution,
        *,
        result: dict[
            str,
            object,
        ],
    ) -> None:
        now = (
            datetime.now(
                UTC
            )
            .isoformat()
        )

        self._update_owned_execution(
            execution=execution,
            update_expression=(
                "SET "
                "#status = :status, "
                "completed_at = :now, "
                "updated_at = :now, "
                "#result = :result "
                "REMOVE "
                "lease_expires_at, "
                "reconciliation_started_at, "
                "reconciliation_token, "
                "last_error"
            ),
            expression_attribute_names={
                "#status": "status",
                "#result": "result",
            },
            expression_attribute_values={
                ":status": (
                    IncidentTaskExecutionStatus
                    .SUCCEEDED
                    .value
                ),
                ":now": now,
                ":result": result,
            },
        )

    def mark_retryable_failure(
        self,
        execution: IncidentTaskExecution,
        *,
        error: str,
    ) -> None:
        now = (
            datetime.now(
                UTC
            )
            .isoformat()
        )

        self._update_owned_execution(
            execution=execution,
            update_expression=(
                "SET "
                "#status = :status, "
                "updated_at = :now, "
                "last_error = :error "
                "REMOVE "
                "lease_expires_at, "
                "reconciliation_started_at, "
                "reconciliation_token"
            ),
            expression_attribute_names={
                "#status": "status",
            },
            expression_attribute_values={
                ":status": (
                    IncidentTaskExecutionStatus
                    .READY_FOR_INCIDENT_SERVICE
                    .value
                ),
                ":now": now,
                ":error": (
                    error[
                        :1000
                    ]
                ),
            },
        )

    def mark_failed(
        self,
        execution: IncidentTaskExecution,
        *,
        error: str,
    ) -> None:
        now = (
            datetime.now(
                UTC
            )
            .isoformat()
        )

        self._update_owned_execution(
            execution=execution,
            update_expression=(
                "SET "
                "#status = :status, "
                "failed_at = :now, "
                "updated_at = :now, "
                "last_error = :error "
                "REMOVE "
                "lease_expires_at, "
                "reconciliation_started_at, "
                "reconciliation_token"
            ),
            expression_attribute_names={
                "#status": "status",
            },
            expression_attribute_values={
                ":status": (
                    IncidentTaskExecutionStatus
                    .FAILED
                    .value
                ),
                ":now": now,
                ":error": (
                    error[
                        :1000
                    ]
                ),
            },
        )

    def _query_status(
        self,
        *,
        status: IncidentTaskExecutionStatus,
        limit: int,
    ) -> list[
        dict[str, Any]
    ]:
        response = (
            self._table.query(
                IndexName=(
                    self
                    ._status_index_name
                ),
                KeyConditionExpression=(
                    "#status = :status"
                ),
                ExpressionAttributeNames={
                    "#status": (
                        "status"
                    ),
                },
                ExpressionAttributeValues={
                    ":status": (
                        status.value
                    ),
                },
                ScanIndexForward=True,
                Limit=limit,
            )
        )

        items = response.get(
            "Items",
            [],
        )

        return [
            item
            for item in items
            if isinstance(
                item,
                dict,
            )
        ]

    def _query_expired_processing(
        self,
        *,
        limit: int,
    ) -> list[
        dict[str, Any]
    ]:
        now_epoch = int(
            time()
        )

        response = (
            self._table.query(
                IndexName=(
                    self
                    ._status_index_name
                ),
                KeyConditionExpression=(
                    "#status = :status"
                ),
                FilterExpression=(
                    "attribute_exists("
                    "lease_expires_at"
                    ") AND "
                    "lease_expires_at <= :now_epoch"
                ),
                ExpressionAttributeNames={
                    "#status": (
                        "status"
                    ),
                },
                ExpressionAttributeValues={
                    ":status": (
                        IncidentTaskExecutionStatus
                        .INCIDENT_SERVICE_PROCESSING
                        .value
                    ),
                    ":now_epoch": (
                        now_epoch
                    ),
                },
                ScanIndexForward=True,
                Limit=limit,
            )
        )

        items = response.get(
            "Items",
            [],
        )

        return [
            item
            for item in items
            if isinstance(
                item,
                dict,
            )
        ]

    def _update_owned_execution(
        self,
        *,
        execution: IncidentTaskExecution,
        update_expression: str,
        expression_attribute_names: dict[
            str,
            str,
        ],
        expression_attribute_values: dict[
            str,
            object,
        ],
    ) -> None:
        token = (
            execution
            .reconciliation_token
        )

        if token is None:
            raise (
                ExecutionStateOwnershipLostError(
                    "Execution has no reconciliation token."
                )
            )

        values = {
            **expression_attribute_values,
            ":processing": (
                IncidentTaskExecutionStatus
                .INCIDENT_SERVICE_PROCESSING
                .value
            ),
            ":token": token,
        }

        try:
            self._table.update_item(
                Key={
                    "task_id": (
                        execution.task_id
                    ),
                },
                UpdateExpression=(
                    update_expression
                ),
                ConditionExpression=(
                    "#status = :processing "
                    "AND reconciliation_token = :token"
                ),
                ExpressionAttributeNames=(
                    expression_attribute_names
                ),
                ExpressionAttributeValues=(
                    values
                ),
            )

        except ClientError as exc:
            if (
                self._error_code(
                    exc
                )
                == (
                    "ConditionalCheckFailedException"
                )
            ):
                raise (
                    ExecutionStateOwnershipLostError(
                        "Reconciler no longer owns "
                        f"task {execution.task_id}."
                    )
                ) from exc

            raise

    @staticmethod
    def _to_domain(
        item: dict[
            str,
            Any,
        ],
    ) -> IncidentTaskExecution:
        lease_value = item.get(
            "lease_expires_at"
        )

        token_value = item.get(
            "reconciliation_token"
        )

        return (
            IncidentTaskExecution(
                task_id=str(
                    item[
                        "task_id"
                    ]
                ),
                incident_id=UUID(
                    str(
                        item[
                            "incident_id"
                        ]
                    )
                ),
                task_type=str(
                    item[
                        "task_type"
                    ]
                ),
                correlation_id=str(
                    item[
                        "correlation_id"
                    ]
                ),
                created_at=str(
                    item[
                        "created_at"
                    ]
                ),
                status=(
                    IncidentTaskExecutionStatus(
                        str(
                            item[
                                "status"
                            ]
                        )
                    )
                ),
                reconciliation_attempts=int(
                    item.get(
                        "reconciliation_attempts",
                        0,
                    )
                ),
                lease_expires_at=(
                    int(
                        lease_value
                    )
                    if (
                        lease_value
                        is not None
                    )
                    else None
                ),
                reconciliation_token=(
                    str(
                        token_value
                    )
                    if (
                        token_value
                        is not None
                    )
                    else None
                ),
            )
        )

    @staticmethod
    def _error_code(
        exc: ClientError,
    ) -> str | None:
        return (
            exc.response
            .get(
                "Error",
                {},
            )
            .get(
                "Code"
            )
        )
