from __future__ import annotations

import pytest

from app.core.circuit_breaker import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
)


class FakeClock:
    def __init__(
        self,
    ) -> None:
        self.current_seconds = 0.0

    def __call__(
        self,
    ) -> float:
        return (
            self.current_seconds
        )

    def advance(
        self,
        seconds: float,
    ) -> None:
        self.current_seconds += (
            seconds
        )


def test_circuit_opens_at_failure_threshold(
) -> None:
    clock = FakeClock()

    circuit = CircuitBreaker(
        failure_threshold=2,
        recovery_seconds=10.0,
        clock=clock,
    )

    first_permit = (
        circuit.acquire_permission()
    )

    circuit.record_failure(
        first_permit
    )

    assert (
        circuit.state
        is CircuitState.CLOSED
    )

    assert (
        circuit.consecutive_failures
        == 1
    )

    second_permit = (
        circuit.acquire_permission()
    )

    circuit.record_failure(
        second_permit
    )

    assert (
        circuit.state
        is CircuitState.OPEN
    )

    assert (
        circuit.consecutive_failures
        == 2
    )

    with pytest.raises(
        CircuitOpenError
    ) as captured_error:
        circuit.acquire_permission()

    assert (
        captured_error
        .value
        .retry_after_seconds
        == 10.0
    )


def test_success_resets_closed_failure_count(
) -> None:
    circuit = CircuitBreaker(
        failure_threshold=3,
        recovery_seconds=10.0,
    )

    failed_permit = (
        circuit.acquire_permission()
    )

    circuit.record_failure(
        failed_permit
    )

    assert (
        circuit.consecutive_failures
        == 1
    )

    successful_permit = (
        circuit.acquire_permission()
    )

    circuit.record_success(
        successful_permit
    )

    assert (
        circuit.state
        is CircuitState.CLOSED
    )

    assert (
        circuit.consecutive_failures
        == 0
    )


def test_recovery_allows_only_one_half_open_probe(
) -> None:
    clock = FakeClock()

    circuit = CircuitBreaker(
        failure_threshold=1,
        recovery_seconds=10.0,
        clock=clock,
    )

    failed_permit = (
        circuit.acquire_permission()
    )

    circuit.record_failure(
        failed_permit
    )

    clock.advance(
        10.0
    )

    probe_permit = (
        circuit.acquire_permission()
    )

    assert (
        probe_permit
        .is_half_open_probe
        is True
    )

    assert (
        circuit.state
        is CircuitState.HALF_OPEN
    )

    with pytest.raises(
        CircuitOpenError
    ) as captured_error:
        circuit.acquire_permission()

    assert (
        captured_error
        .value
        .retry_after_seconds
        == 1.0
    )

    circuit.record_success(
        probe_permit
    )

    assert (
        circuit.state
        is CircuitState.CLOSED
    )

    assert (
        circuit.consecutive_failures
        == 0
    )


def test_failed_half_open_probe_reopens_for_full_interval(
) -> None:
    clock = FakeClock()

    circuit = CircuitBreaker(
        failure_threshold=1,
        recovery_seconds=10.0,
        clock=clock,
    )

    initial_permit = (
        circuit.acquire_permission()
    )

    circuit.record_failure(
        initial_permit
    )

    clock.advance(
        10.0
    )

    probe_permit = (
        circuit.acquire_permission()
    )

    circuit.record_failure(
        probe_permit
    )

    assert (
        circuit.state
        is CircuitState.OPEN
    )

    with pytest.raises(
        CircuitOpenError
    ) as captured_error:
        circuit.acquire_permission()

    assert (
        captured_error
        .value
        .retry_after_seconds
        == 10.0
    )


def test_stale_success_cannot_close_newly_opened_circuit(
) -> None:
    clock = FakeClock()

    circuit = CircuitBreaker(
        failure_threshold=1,
        recovery_seconds=10.0,
        clock=clock,
    )

    first_permit = (
        circuit.acquire_permission()
    )

    stale_permit = (
        circuit.acquire_permission()
    )

    circuit.record_failure(
        first_permit
    )

    assert (
        circuit.state
        is CircuitState.OPEN
    )

    circuit.record_success(
        stale_permit
    )

    assert (
        circuit.state
        is CircuitState.OPEN
    )


@pytest.mark.parametrize(
    (
        "failure_threshold",
        "recovery_seconds",
        "expected_message",
    ),
    [
        (
            0,
            10.0,
            "failure_threshold",
        ),
        (
            1,
            0.0,
            "recovery_seconds",
        ),
    ],
)
def test_invalid_circuit_configuration_is_rejected(
    failure_threshold: int,
    recovery_seconds: float,
    expected_message: str,
) -> None:
    with pytest.raises(
        ValueError,
        match=expected_message,
    ):
        CircuitBreaker(
            failure_threshold=(
                failure_threshold
            ),
            recovery_seconds=(
                recovery_seconds
            ),
        )