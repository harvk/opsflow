from __future__ import annotations

from uuid import (
    UUID,
)

import pytest

from app.messaging import (
    DEFAULT_IDEMPOTENCY_VERSION,
    GENERATED_CORRELATION_PREFIX,
    build_idempotency_key,
    resolve_correlation_id,
)

# =========================================================
# TEST VALUES
# =========================================================

INCIDENT_ID = (
    "11111111-1111-4111-8111-111111111111"
)

SCOPE = (
    "incident"
)

OPERATION = (
    "notification-requested"
)


# =========================================================
# IDEMPOTENCY KEY CONTRACT
# =========================================================


def test_build_idempotency_key_is_deterministic(
) -> None:
    first = build_idempotency_key(
        scope=SCOPE,
        resource_id=INCIDENT_ID,
        operation=OPERATION,
    )

    second = build_idempotency_key(
        scope=SCOPE,
        resource_id=INCIDENT_ID,
        operation=OPERATION,
    )

    assert (
        first
        == second
    )


def test_build_idempotency_key_has_canonical_format(
) -> None:
    key = build_idempotency_key(
        scope=SCOPE,
        resource_id=INCIDENT_ID,
        operation=OPERATION,
    )

    assert (
        key
        == (
            "incident:"
            "11111111-1111-4111-8111-111111111111:"
            "notification-requested:"
            "v1"
        )
    )


def test_build_idempotency_key_trims_segments(
) -> None:
    key = build_idempotency_key(
        scope="  incident  ",
        resource_id=(
            "  "
            "11111111-1111-4111-8111-111111111111"
            "  "
        ),
        operation=(
            "  notification-requested  "
        ),
    )

    assert (
        key
        == (
            "incident:"
            "11111111-1111-4111-8111-111111111111:"
            "notification-requested:"
            "v1"
        )
    )


def test_build_idempotency_key_supports_versioning(
) -> None:
    version_one = build_idempotency_key(
        scope=SCOPE,
        resource_id=INCIDENT_ID,
        operation=OPERATION,
        version=1,
    )

    version_two = build_idempotency_key(
        scope=SCOPE,
        resource_id=INCIDENT_ID,
        operation=OPERATION,
        version=2,
    )

    assert (
        version_one
        != version_two
    )

    assert (
        version_one.endswith(
            ":v1"
        )
    )

    assert (
        version_two.endswith(
            ":v2"
        )
    )


def test_default_idempotency_version_is_one(
) -> None:
    assert (
        DEFAULT_IDEMPOTENCY_VERSION
        == 1
    )


@pytest.mark.parametrize(
    (
        "field_name",
        "scope",
        "resource_id",
        "operation",
    ),
    [
        (
            "scope",
            "   ",
            INCIDENT_ID,
            OPERATION,
        ),
        (
            "resource_id",
            SCOPE,
            "   ",
            OPERATION,
        ),
        (
            "operation",
            SCOPE,
            INCIDENT_ID,
            "   ",
        ),
    ],
)
def test_build_idempotency_key_rejects_blank_segments(
    field_name: str,
    scope: str,
    resource_id: str,
    operation: str,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            rf"{field_name} must not be blank"
        ),
    ):
        build_idempotency_key(
            scope=scope,
            resource_id=resource_id,
            operation=operation,
        )


@pytest.mark.parametrize(
    (
        "field_name",
        "scope",
        "resource_id",
        "operation",
    ),
    [
        (
            "scope",
            "incident:external",
            INCIDENT_ID,
            OPERATION,
        ),
        (
            "resource_id",
            SCOPE,
            "incident:123",
            OPERATION,
        ),
        (
            "operation",
            SCOPE,
            INCIDENT_ID,
            "notification:requested",
        ),
    ],
)
def test_build_idempotency_key_rejects_separator_in_segments(
    field_name: str,
    scope: str,
    resource_id: str,
    operation: str,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            rf"{field_name} must not contain"
        ),
    ):
        build_idempotency_key(
            scope=scope,
            resource_id=resource_id,
            operation=operation,
        )


@pytest.mark.parametrize(
    "version",
    [
        0,
        -1,
        -100,
    ],
)
def test_build_idempotency_key_rejects_invalid_version(
    version: int,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "version must be greater than or equal to 1"
        ),
    ):
        build_idempotency_key(
            scope=SCOPE,
            resource_id=INCIDENT_ID,
            operation=OPERATION,
            version=version,
        )


# =========================================================
# CORRELATION ID CONTRACT
# =========================================================


def test_resolve_correlation_id_preserves_existing_id(
) -> None:
    correlation_id = (
        "request:"
        "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    )

    resolved = (
        resolve_correlation_id(
            correlation_id
        )
    )

    assert (
        resolved
        == correlation_id
    )


def test_resolve_correlation_id_trims_existing_id(
) -> None:
    resolved = (
        resolve_correlation_id(
            "  request:test-correlation  "
        )
    )

    assert (
        resolved
        == "request:test-correlation"
    )


@pytest.mark.parametrize(
    "correlation_id",
    [
        None,
        "",
        "   ",
    ],
)
def test_resolve_correlation_id_generates_fallback(
    correlation_id: str | None,
) -> None:
    resolved = (
        resolve_correlation_id(
            correlation_id
        )
    )

    prefix = (
        f"{GENERATED_CORRELATION_PREFIX}:"
    )

    assert resolved.startswith(
        prefix
    )

    generated_uuid = (
        resolved.removeprefix(
            prefix
        )
    )

    parsed = UUID(
        generated_uuid
    )

    assert (
        str(
            parsed
        )
        == generated_uuid
    )


def test_generated_correlation_ids_are_unique(
) -> None:
    first = (
        resolve_correlation_id(
            None
        )
    )

    second = (
        resolve_correlation_id(
            None
        )
    )

    assert (
        first
        != second
    )


# =========================================================
# IDENTITY SEPARATION
# =========================================================


def test_correlation_id_is_independent_from_idempotency_key(
) -> None:
    idempotency_key = (
        build_idempotency_key(
            scope=SCOPE,
            resource_id=INCIDENT_ID,
            operation=OPERATION,
        )
    )

    correlation_id = (
        resolve_correlation_id(
            None
        )
    )

    assert (
        correlation_id
        != idempotency_key
    )
