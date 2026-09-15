from __future__ import annotations

from collections.abc import (
    Callable,
)
from dataclasses import (
    dataclass,
)
from enum import (
    Enum,
)
from threading import (
    Lock,
)
from time import (
    monotonic,
)


class CircuitState(
    str,
    Enum,
):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass(
    frozen=True,
    slots=True,
)
class CircuitPermit:
    """
    Permission for one logical dependency operation.

    generation prevents an older in-flight request from
    resetting a circuit that was opened by newer results.
    """

    generation: int
    is_half_open_probe: bool


class CircuitOpenError(
    RuntimeError
):
    """
    Raised when the circuit rejects an operation before any
    dependency call is made.
    """

    def __init__(
        self,
        *,
        retry_after_seconds: float,
    ) -> None:
        self.retry_after_seconds = max(
            retry_after_seconds,
            0.0,
        )

        super().__init__(
            "Circuit breaker is open."
        )


class CircuitBreaker:
    """
    Thread-safe, process-local circuit breaker.

    Backend synchronous routes execute in worker threads.
    The breaker therefore protects all mutable state with a
    threading.Lock.

    One CircuitBreaker instance must be shared by every
    HttpIncidentGateway instance in the Backend process.
    """

    def __init__(
        self,
        *,
        failure_threshold: int,
        recovery_seconds: float,
        clock: Callable[
            [],
            float,
        ] = monotonic,
    ) -> None:
        if failure_threshold < 1:
            raise ValueError(
                "failure_threshold must be at least 1."
            )

        if recovery_seconds <= 0:
            raise ValueError(
                "recovery_seconds must be greater than 0."
            )

        self._failure_threshold = (
            failure_threshold
        )

        self._recovery_seconds = (
            recovery_seconds
        )

        self._clock = clock

        self._lock = (
            Lock()
        )

        self._state = (
            CircuitState.CLOSED
        )

        self._consecutive_failures = 0

        self._opened_at: (
            float | None
        ) = None

        self._generation = 0

    @property
    def state(
        self,
    ) -> CircuitState:
        with self._lock:
            return self._state

    @property
    def consecutive_failures(
        self,
    ) -> int:
        with self._lock:
            return (
                self._consecutive_failures
            )

    def acquire_permission(
        self,
    ) -> CircuitPermit:
        """
        Return permission for one logical dependency call.

        When the recovery interval has elapsed, exactly one
        caller changes the circuit to half-open and receives
        permission to perform the probe. Other concurrent
        callers continue to fail fast.
        """

        with self._lock:
            if (
                self._state
                is CircuitState.CLOSED
            ):
                return CircuitPermit(
                    generation=(
                        self._generation
                    ),
                    is_half_open_probe=False,
                )

            if (
                self._state
                is CircuitState.HALF_OPEN
            ):
                raise CircuitOpenError(
                    retry_after_seconds=1.0
                )

            current_time = (
                self._clock()
            )

            opened_at = (
                self._opened_at
            )

            if opened_at is None:
                remaining_seconds = (
                    self._recovery_seconds
                )

            else:
                elapsed_seconds = (
                    current_time
                    - opened_at
                )

                remaining_seconds = (
                    self._recovery_seconds
                    - elapsed_seconds
                )

            if remaining_seconds > 0:
                raise CircuitOpenError(
                    retry_after_seconds=(
                        remaining_seconds
                    )
                )

            self._state = (
                CircuitState.HALF_OPEN
            )

            return CircuitPermit(
                generation=(
                    self._generation
                ),
                is_half_open_probe=True,
            )

    def record_success(
        self,
        permit: CircuitPermit,
    ) -> None:
        """
        Close the circuit after a successful half-open probe,
        or reset the closed-state consecutive-failure count.

        Results from an older generation are ignored.
        """

        with self._lock:
            if (
                permit.generation
                != self._generation
            ):
                return

            if permit.is_half_open_probe:
                if (
                    self._state
                    is not CircuitState.HALF_OPEN
                ):
                    return

                self._state = (
                    CircuitState.CLOSED
                )

                self._consecutive_failures = 0
                self._opened_at = None

                # Invalidate any older in-flight permits.
                self._generation += 1

                return

            if (
                self._state
                is CircuitState.CLOSED
            ):
                self._consecutive_failures = 0

    def record_failure(
        self,
        permit: CircuitPermit,
    ) -> None:
        """
        Record one failed logical dependency operation.

        Retry attempts within that operation are deliberately
        not counted separately.
        """

        with self._lock:
            if (
                permit.generation
                != self._generation
            ):
                return

            if permit.is_half_open_probe:
                if (
                    self._state
                    is CircuitState.HALF_OPEN
                ):
                    self._open_locked(
                        self._clock()
                    )

                return

            if (
                self._state
                is not CircuitState.CLOSED
            ):
                return

            self._consecutive_failures += 1

            if (
                self._consecutive_failures
                >= self._failure_threshold
            ):
                self._open_locked(
                    self._clock()
                )

    def _open_locked(
        self,
        opened_at: float,
    ) -> None:
        """
        Open the circuit while self._lock is already held.
        """

        self._state = (
            CircuitState.OPEN
        )

        self._opened_at = (
            opened_at
        )

        # The count is retained at the threshold for
        # operational inspection rather than growing without
        # a bound during an outage.
        self._consecutive_failures = (
            self._failure_threshold
        )

        # Invalidate older in-flight permits.
        self._generation += 1