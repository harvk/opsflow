from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
import hmac
from threading import RLock
from time import monotonic
from typing import Literal, Protocol


ThrottleReason = Literal[
    "ip",
    "account",
]


@dataclass(
    frozen=True,
    slots=True,
)
class LoginThrottleDecision:
    """
    Internal result returned by the authentication throttle.

    blocked_by is deliberately an internal diagnostic value.
    It must never be exposed to the HTTP client because doing
    so would reveal useful information to an attacker.
    """

    allowed: bool

    blocked_by: (
        ThrottleReason
        | None
    ) = None


class LoginThrottle(Protocol):
    """
    Abstraction for login-attempt throttling.

    The HTTP authentication layer depends on this contract
    rather than depending directly on an in-memory data
    structure.

    That becomes important later when the backing
    implementation moves to Redis.
    """

    def begin_attempt(
        self,
        *,
        client_address: str,
        account_identifier: str,
    ) -> LoginThrottleDecision:
        """
        Determine whether another authentication attempt may
        proceed.

        The source-IP attempt is counted regardless of whether
        authentication ultimately succeeds.
        """

        ...

    def record_failure(
        self,
        *,
        account_identifier: str,
    ) -> None:
        """
        Record a failed password authentication attempt.
        """

        ...

    def record_success(
        self,
        *,
        account_identifier: str,
    ) -> None:
        """
        Clear accumulated account failures following
        successful authentication.
        """

        ...


class InMemoryLoginThrottle:
    """
    Thread-safe development/test implementation of
    LoginThrottle.

    Two completely independent sliding-window buckets are
    maintained:

        1. source IP login attempts
        2. account authentication failures

    IMPORTANT:

    This implementation is intentionally suitable for local
    development, tests, and a single application process.

    It is NOT the final distributed production implementation.

    Multiple Uvicorn/Gunicorn workers would each maintain
    separate memory, allowing the effective rate limit to be
    multiplied by the number of workers.

    OpsFlow will later replace this adapter with Redis while
    leaving the LoginThrottle interface unchanged.
    """

    def __init__(
        self,
        *,
        secret_key: str,
        ip_max_attempts: int,
        ip_window_seconds: int,
        account_max_failures: int,
        account_window_seconds: int,
        clock: Callable[
            [],
            float,
        ] = monotonic,
    ) -> None:
        if not secret_key:
            raise ValueError(
                "A login throttle secret is required."
            )

        if ip_max_attempts <= 0:
            raise ValueError(
                "ip_max_attempts must be positive."
            )

        if ip_window_seconds <= 0:
            raise ValueError(
                "ip_window_seconds must be positive."
            )

        if account_max_failures <= 0:
            raise ValueError(
                "account_max_failures must be positive."
            )

        if account_window_seconds <= 0:
            raise ValueError(
                "account_window_seconds must be positive."
            )

        self._secret_key = (
            secret_key.encode(
                "utf-8"
            )
        )

        self._ip_max_attempts = (
            ip_max_attempts
        )

        self._ip_window_seconds = (
            float(
                ip_window_seconds
            )
        )

        self._account_max_failures = (
            account_max_failures
        )

        self._account_window_seconds = (
            float(
                account_window_seconds
            )
        )

        self._clock = clock

        self._ip_attempts: dict[
            str,
            deque[float],
        ] = {}

        self._account_failures: dict[
            str,
            deque[float],
        ] = {}

        self._lock = RLock()

    # =====================================================
    # PUBLIC API
    # =====================================================

    def begin_attempt(
        self,
        *,
        client_address: str,
        account_identifier: str,
    ) -> LoginThrottleDecision:
        now = self._clock()

        ip_key = self._opaque_key(
            namespace="ip",
            value=client_address,
        )

        account_key = self._account_key(
            account_identifier
        )

        with self._lock:
            ip_attempts = (
                self._get_active_entries(
                    storage=self._ip_attempts,
                    key=ip_key,
                    now=now,
                    window_seconds=(
                        self._ip_window_seconds
                    ),
                )
            )

            if (
                len(ip_attempts)
                >= self._ip_max_attempts
            ):
                return LoginThrottleDecision(
                    allowed=False,
                    blocked_by="ip",
                )

            # Count every login submission that reaches this
            # stage, including requests later rejected by the
            # per-account throttle.
            ip_attempts.append(
                now
            )

            account_failures = (
                self._get_active_entries(
                    storage=(
                        self._account_failures
                    ),
                    key=account_key,
                    now=now,
                    window_seconds=(
                        self
                        ._account_window_seconds
                    ),
                )
            )

            if (
                len(account_failures)
                >= self._account_max_failures
            ):
                return LoginThrottleDecision(
                    allowed=False,
                    blocked_by="account",
                )

            return LoginThrottleDecision(
                allowed=True
            )

    def record_failure(
        self,
        *,
        account_identifier: str,
    ) -> None:
        now = self._clock()

        account_key = self._account_key(
            account_identifier
        )

        with self._lock:
            account_failures = (
                self._get_active_entries(
                    storage=(
                        self._account_failures
                    ),
                    key=account_key,
                    now=now,
                    window_seconds=(
                        self
                        ._account_window_seconds
                    ),
                )
            )

            account_failures.append(
                now
            )

    def record_success(
        self,
        *,
        account_identifier: str,
    ) -> None:
        account_key = self._account_key(
            account_identifier
        )

        with self._lock:
            self._account_failures.pop(
                account_key,
                None,
            )

    def reset(
        self,
    ) -> None:
        """
        Clear all in-memory throttle state.

        This primarily exists so pytest tests remain isolated.
        """

        with self._lock:
            self._ip_attempts.clear()
            self._account_failures.clear()

    # =====================================================
    # INTERNAL KEY HANDLING
    # =====================================================

    def _account_key(
        self,
        account_identifier: str,
    ) -> str:
        normalized_identifier = (
            account_identifier
            .strip()
            .lower()
        )

        return self._opaque_key(
            namespace="account",
            value=normalized_identifier,
        )

    def _opaque_key(
        self,
        *,
        namespace: str,
        value: str,
    ) -> str:
        """
        Avoid storing raw emails or IP addresses as dictionary
        keys.

        HMAC also prevents an attacker who somehow observes
        throttle storage from trivially mapping keys back to
        account identifiers.
        """

        message = (
            f"{namespace}:{value}"
            .encode(
                "utf-8"
            )
        )

        return hmac.new(
            self._secret_key,
            message,
            sha256,
        ).hexdigest()

    # =====================================================
    # SLIDING WINDOW
    # =====================================================

    @staticmethod
    def _prune(
        entries: deque[float],
        *,
        cutoff: float,
    ) -> None:
        while (
            entries
            and entries[0] <= cutoff
        ):
            entries.popleft()

    def _get_active_entries(
        self,
        *,
        storage: dict[
            str,
            deque[float],
        ],
        key: str,
        now: float,
        window_seconds: float,
    ) -> deque[float]:
        entries = storage.setdefault(
            key,
            deque(),
        )

        self._prune(
            entries,
            cutoff=(
                now
                - window_seconds
            ),
        )

        return entries