from __future__ import annotations

from uuid import (
    uuid4,
)

# =========================================================
# TASK IDENTITY CONSTANTS
# =========================================================

IDEMPOTENCY_KEY_SEPARATOR = ":"

DEFAULT_IDEMPOTENCY_VERSION = 1

GENERATED_CORRELATION_PREFIX = (
    "corr"
)


# =========================================================
# INTERNAL VALIDATION
# =========================================================


def _normalize_identity_segment(
    *,
    name: str,
    value: str,
) -> str:
    """
    Normalize one segment used in a distributed task
    identity.

    Identity segments must be non-empty and may not contain
    the separator used by the canonical idempotency-key
    format.
    """

    normalized = (
        value.strip()
    )

    if not normalized:
        raise ValueError(
            f"{name} must not be blank."
        )

    if (
        IDEMPOTENCY_KEY_SEPARATOR
        in normalized
    ):
        raise ValueError(
            f"{name} must not contain "
            f"'{IDEMPOTENCY_KEY_SEPARATOR}'."
        )

    return normalized


# =========================================================
# IDEMPOTENCY IDENTITY
# =========================================================


def build_idempotency_key(
    *,
    scope: str,
    resource_id: str,
    operation: str,
    version: int = (
        DEFAULT_IDEMPOTENCY_VERSION
    ),
) -> str:
    """
    Build the canonical OpsFlow idempotency key for one
    logical business operation.

    The result is deterministic. Supplying the same
    normalized inputs always produces the same key.

    Format:

        <scope>:<resource_id>:<operation>:v<version>

    Example:

        incident:
        11111111-1111-4111-8111-111111111111:
        notification-requested:
        v1

    task_id, timestamps, request IDs, and SQS message IDs
    must never be incorporated into this value.
    """

    normalized_scope = (
        _normalize_identity_segment(
            name="scope",
            value=scope,
        )
    )

    normalized_resource_id = (
        _normalize_identity_segment(
            name="resource_id",
            value=resource_id,
        )
    )

    normalized_operation = (
        _normalize_identity_segment(
            name="operation",
            value=operation,
        )
    )

    if version < 1:
        raise ValueError(
            "version must be greater than or equal to 1."
        )

    return (
        f"{normalized_scope}"
        f"{IDEMPOTENCY_KEY_SEPARATOR}"
        f"{normalized_resource_id}"
        f"{IDEMPOTENCY_KEY_SEPARATOR}"
        f"{normalized_operation}"
        f"{IDEMPOTENCY_KEY_SEPARATOR}"
        f"v{version}"
    )


# =========================================================
# CORRELATION IDENTITY
# =========================================================


def resolve_correlation_id(
    correlation_id: str | None,
) -> str:
    """
    Preserve an existing workflow/request correlation ID.

    When no usable correlation ID exists, generate one for
    the new workflow boundary.

    Correlation identity is intentionally independent from
    task identity and idempotency identity.
    """

    if correlation_id is not None:
        normalized = (
            correlation_id.strip()
        )

        if normalized:
            return normalized

    return (
        f"{GENERATED_CORRELATION_PREFIX}:"
        f"{uuid4()}"
    )
