from __future__ import annotations

from datetime import (
    UTC,
    datetime,
)
from uuid import (
    UUID,
)

import pytest
from pydantic import (
    ValidationError,
)

from app.messaging.task_envelope import (
    TASK_KIND,
    TASK_SCHEMA_VERSION,
    TaskEnvelope,
)

# =========================================================
# TEST VALUES
# =========================================================

TASK_TYPE = (
    "incident.notification.requested"
)

PRODUCER = (
    "opsflow-api"
)

CORRELATION_ID = (
    "request:test-correlation"
)

IDEMPOTENCY_KEY = (
    "incident-notification:"
    "11111111-1111-4111-8111-111111111111:"
    "created"
)

FIXED_TASK_ID = (
    "22222222-2222-4222-8222-222222222222"
)

FIXED_CREATED_AT = datetime(
    2026,
    9,
    18,
    20,
    30,
    0,
    tzinfo=UTC,
)


# =========================================================
# TEST HELPERS
# =========================================================


def build_envelope(
    **overrides: object,
) -> TaskEnvelope:
    values: dict[
        str,
        object,
    ] = {
        "task_id": FIXED_TASK_ID,
        "task_type": TASK_TYPE,
        "created_at": FIXED_CREATED_AT,
        "producer": PRODUCER,
        "correlation_id": CORRELATION_ID,
        "idempotency_key": IDEMPOTENCY_KEY,
        "payload": {
            "incident_id": (
                "11111111-1111-4111-8111-111111111111"
            ),
            "customer_impacting": True,
        },
    }

    values.update(
        overrides
    )

    return TaskEnvelope.model_validate(
        values
    )


# =========================================================
# DEFAULT CONTRACT
# =========================================================


def test_task_envelope_generates_message_identity_and_timestamp(
) -> None:
    envelope = TaskEnvelope(
        task_type=TASK_TYPE,
        producer=PRODUCER,
        correlation_id=CORRELATION_ID,
        idempotency_key=IDEMPOTENCY_KEY,
        payload={
            "incident_id": (
                "11111111-1111-4111-8111-111111111111"
            ),
        },
    )

    parsed_task_id = UUID(
        envelope.task_id
    )

    assert str(
        parsed_task_id
    ) == envelope.task_id

    assert (
        envelope.created_at.tzinfo
        is not None
    )

    assert (
        envelope.kind
        == TASK_KIND
    )

    assert (
        envelope.schema_version
        == TASK_SCHEMA_VERSION
    )

    assert (
        envelope.causation_id
        is None
    )

    assert (
        envelope.metadata
        == {}
    )


# =========================================================
# SERIALIZED CONTRACT
# =========================================================


def test_task_envelope_serializes_complete_v1_contract(
) -> None:
    envelope = build_envelope(
        causation_id=(
            "event:incident-created"
        ),
        metadata={
            "source": "backend",
            "priority": "normal",
        },
    )

    serialized = envelope.model_dump(
        mode="json"
    )

    assert set(
        serialized
    ) == {
        "task_id",
        "kind",
        "task_type",
        "schema_version",
        "created_at",
        "producer",
        "correlation_id",
        "idempotency_key",
        "payload",
        "causation_id",
        "metadata",
    }

    assert (
        serialized["task_id"]
        == FIXED_TASK_ID
    )

    assert (
        serialized["kind"]
        == "task"
    )

    assert (
        serialized["task_type"]
        == TASK_TYPE
    )

    assert (
        serialized["schema_version"]
        == "1.0"
    )

    assert (
        serialized["producer"]
        == PRODUCER
    )

    assert (
        serialized["correlation_id"]
        == CORRELATION_ID
    )

    assert (
        serialized["idempotency_key"]
        == IDEMPOTENCY_KEY
    )

    assert (
        serialized["causation_id"]
        == "event:incident-created"
    )

    assert (
        serialized["metadata"]
        == {
            "source": "backend",
            "priority": "normal",
        }
    )

    assert (
        serialized["payload"]
        == {
            "incident_id": (
                "11111111-1111-4111-8111-111111111111"
            ),
            "customer_impacting": True,
        }
    )

    serialized_created_at = (
        str(
            serialized[
                "created_at"
            ]
        )
        .replace(
            "Z",
            "+00:00",
        )
    )

    parsed_created_at = (
        datetime.fromisoformat(
            serialized_created_at
        )
    )

    assert (
        parsed_created_at.tzinfo
        is not None
    )


# =========================================================
# STRING NORMALIZATION
# =========================================================


def test_task_envelope_trims_required_contract_strings(
) -> None:
    envelope = build_envelope(
        task_type=(
            "  incident.notification.requested  "
        ),
        producer=(
            "  opsflow-api  "
        ),
        correlation_id=(
            "  request:123  "
        ),
        idempotency_key=(
            "  incident:123:notification  "
        ),
    )

    assert (
        envelope.task_type
        == "incident.notification.requested"
    )

    assert (
        envelope.producer
        == "opsflow-api"
    )

    assert (
        envelope.correlation_id
        == "request:123"
    )

    assert (
        envelope.idempotency_key
        == "incident:123:notification"
    )


@pytest.mark.parametrize(
    "field_name",
    [
        "task_type",
        "producer",
        "correlation_id",
        "idempotency_key",
    ],
)
def test_task_envelope_rejects_blank_required_strings(
    field_name: str,
) -> None:
    with pytest.raises(
        ValidationError
    ):
        build_envelope(
            **{
                field_name: "   ",
            }
        )


def test_task_envelope_rejects_blank_causation_id_when_present(
) -> None:
    with pytest.raises(
        ValidationError
    ):
        build_envelope(
            causation_id="   "
        )


# =========================================================
# PAYLOAD CONTRACT
# =========================================================


def test_task_envelope_requires_object_payload(
) -> None:
    with pytest.raises(
        ValidationError
    ):
        build_envelope(
            payload=[
                "not",
                "an",
                "object",
            ]
        )


def test_task_envelope_rejects_non_json_payload_values(
) -> None:
    with pytest.raises(
        ValidationError
    ):
        build_envelope(
            payload={
                "invalid": object(),
            }
        )


# =========================================================
# METADATA CONTRACT
# =========================================================


def test_task_envelope_requires_string_metadata_values(
) -> None:
    with pytest.raises(
        ValidationError
    ):
        build_envelope(
            metadata={
                "attempt": 1,
            }
        )


# =========================================================
# STRICT CONTRACT
# =========================================================


def test_task_envelope_rejects_unknown_fields(
) -> None:
    with pytest.raises(
        ValidationError
    ):
        build_envelope(
            unexpected_field=True
        )


def test_task_envelope_rejects_naive_timestamp(
) -> None:
    with pytest.raises(
        ValidationError
    ):
        build_envelope(
            created_at=datetime(  # noqa: DTZ001
                2026,
                9,
                18,
                20,
                30,
                0,
            )
        )