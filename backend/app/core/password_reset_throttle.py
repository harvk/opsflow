from __future__ import annotations

from collections import (
    defaultdict,
    deque,
)

from dataclasses import (
    dataclass,
)

import hashlib
import hmac

from threading import (
    Lock,
)

import time

from typing import (
    Literal,
    Protocol,
)


PasswordResetThrottleBlockReason = Literal[
    "ip",
    "account",
    "ip_and_account",
]


@dataclass(
    frozen=True,
    slots=True,
)
class PasswordResetThrottleDecision:
    """
    Result of evaluating one password-reset request.

    blocked_by is intended for internal security telemetry.
    It must not be exposed through the public HTTP response.
    """

    allowed: bool

    blocked_by: (
        PasswordResetThrottleBlockReason
        | None
    )

    retry_after_seconds: int | None


class PasswordResetThrottle(
    Protocol
):
    """
    Abuse-protection contract for anonymous password-reset
    requests.
    """

    def check_and_record(
        self,
        *,
        client_address: str,
        account_identifier: str,
    ) -> PasswordResetThrottleDecision:
        ...


class InMemoryPasswordResetThrottle:
    """
    Process-local password-reset request limiter.

    Every request counts against two independent buckets:

        source IP address
        normalized account identifier

    Account identifiers are transformed through keyed HMAC
    before being used as in-memory dictionary keys. This
    avoids keeping raw email addresses in throttle state.

    This implementation is appropriate for the current
    single-process application stage. A distributed store
    such as Redis should replace it before horizontally
    scaling the API across multiple workers/instances.
    """

    def __init__(
        self,
        *,
        secret_key: str,
        ip_max_requests: int,
        ip_window_seconds: int,
        account_max_requests: int,
        account_window_seconds: int,
    ) -> None:
        if not secret_key:
            raise ValueError(
                "secret_key must not be empty."
            )

        if ip_max_requests < 1:
            raise ValueError(
                "ip_max_requests must be at least 1."
            )

        if ip_window_seconds < 1:
            raise ValueError(
                "ip_window_seconds must be at least 1."
            )

        if account_max_requests < 1:
            raise ValueError(
                "account_max_requests must be "
                "at least 1."
            )

        if account_window_seconds < 1:
            raise ValueError(
                "account_window_seconds must be "
                "at least 1."
            )

        self._secret_key = (
            secret_key.encode(
                "utf-8"
            )
        )

        self.ip_max_requests = (
            ip_max_requests
        )

        self.ip_window_seconds = (
            ip_window_seconds
        )

        self.account_max_requests = (
            account_max_requests
        )

        self.account_window_seconds = (
            account_window_seconds
        )

        self._ip_requests: dict[
            str,
            deque[float],
        ] = defaultdict(
            deque
        )

        self._account_requests: dict[
            str,
            deque[float],
        ] = defaultdict(
            deque
        )

        self._lock = Lock()

    # =====================================================
    # PUBLIC API
    # =====================================================

    def check_and_record(
        self,
        *,
        client_address: str,
        account_identifier: str,
    ) -> PasswordResetThrottleDecision:
        """
        Atomically evaluate and record one reset request.

        If either bucket is already at capacity, the request
        is denied and is not added to either bucket.

        This avoids a blocked request indefinitely extending
        its own throttle window.
        """

        now = time.monotonic()

        ip_key = (
            self._normalize_client_address(
                client_address
            )
        )

        account_key = (
            self._account_key(
                account_identifier
            )
        )

        with self._lock:
            ip_bucket = (
                self._ip_requests[
                    ip_key
                ]
            )

            account_bucket = (
                self._account_requests[
                    account_key
                ]
            )

            self._prune(
                ip_bucket,
                now=now,
                window_seconds=(
                    self.ip_window_seconds
                ),
            )

            self._prune(
                account_bucket,
                now=now,
                window_seconds=(
                    self.account_window_seconds
                ),
            )

            ip_blocked = (
                len(
                    ip_bucket
                )
                >= self.ip_max_requests
            )

            account_blocked = (
                len(
                    account_bucket
                )
                >= self.account_max_requests
            )

            if (
                ip_blocked
                or account_blocked
            ):
                blocked_by = (
                    self._blocked_by(
                        ip_blocked=(
                            ip_blocked
                        ),
                        account_blocked=(
                            account_blocked
                        ),
                    )
                )

                retry_after_seconds = (
                    self._retry_after(
                        now=now,
                        ip_bucket=(
                            ip_bucket
                        ),
                        account_bucket=(
                            account_bucket
                        ),
                        ip_blocked=(
                            ip_blocked
                        ),
                        account_blocked=(
                            account_blocked
                        ),
                    )
                )

                return (
                    PasswordResetThrottleDecision(
                        allowed=False,
                        blocked_by=(
                            blocked_by
                        ),
                        retry_after_seconds=(
                            retry_after_seconds
                        ),
                    )
                )

            ip_bucket.append(
                now
            )

            account_bucket.append(
                now
            )

            return (
                PasswordResetThrottleDecision(
                    allowed=True,
                    blocked_by=None,
                    retry_after_seconds=None,
                )
            )

    # =====================================================
    # IDENTIFIER PROTECTION
    # =====================================================

    @staticmethod
    def _normalize_client_address(
        client_address: str,
    ) -> str:
        normalized = (
            client_address
            .strip()
            .lower()
        )

        if not normalized:
            return "unknown"

        return normalized

    @staticmethod
    def _normalize_account_identifier(
        account_identifier: str,
    ) -> str:
        return (
            account_identifier
            .strip()
            .lower()
        )

    def _account_key(
        self,
        account_identifier: str,
    ) -> str:
        normalized_identifier = (
            self
            ._normalize_account_identifier(
                account_identifier
            )
        )

        return (
            hmac.new(
                self._secret_key,
                normalized_identifier.encode(
                    "utf-8"
                ),
                hashlib.sha256,
            )
            .hexdigest()
        )

    # =====================================================
    # WINDOW MANAGEMENT
    # =====================================================

    @staticmethod
    def _prune(
        bucket: deque[float],
        *,
        now: float,
        window_seconds: int,
    ) -> None:
        cutoff = (
            now
            - window_seconds
        )

        while (
            bucket
            and bucket[0]
            <= cutoff
        ):
            bucket.popleft()

    @staticmethod
    def _blocked_by(
        *,
        ip_blocked: bool,
        account_blocked: bool,
    ) -> PasswordResetThrottleBlockReason:
        if (
            ip_blocked
            and account_blocked
        ):
            return "ip_and_account"

        if ip_blocked:
            return "ip"

        return "account"

    def _retry_after(
        self,
        *,
        now: float,
        ip_bucket: deque[float],
        account_bucket: deque[float],
        ip_blocked: bool,
        account_blocked: bool,
    ) -> int:
        remaining_windows: list[
            float
        ] = []

        if (
            ip_blocked
            and ip_bucket
        ):
            remaining_windows.append(
                (
                    ip_bucket[0]
                    + self.ip_window_seconds
                )
                - now
            )

        if (
            account_blocked
            and account_bucket
        ):
            remaining_windows.append(
                (
                    account_bucket[0]
                    + self.account_window_seconds
                )
                - now
            )

        if not remaining_windows:
            return 1

        # Round upward without importing math.ceil so a
        # partially remaining second never becomes Retry-After
        # zero.
        longest_remaining = max(
            remaining_windows
        )

        whole_seconds = int(
            longest_remaining
        )

        if (
            longest_remaining
            > whole_seconds
        ):
            whole_seconds += 1

        return max(
            1,
            whole_seconds,
        )