from app.core.login_throttle import (
    InMemoryLoginThrottle,
)


class FakeClock:
    def __init__(
        self,
    ) -> None:
        self.value = 0.0

    def __call__(
        self,
    ) -> float:
        return self.value

    def advance(
        self,
        seconds: float,
    ) -> None:
        self.value += seconds


def create_throttle(
    clock: FakeClock,
    *,
    ip_max_attempts: int = 3,
    ip_window_seconds: int = 60,
    account_max_failures: int = 2,
    account_window_seconds: int = 300,
) -> InMemoryLoginThrottle:
    return InMemoryLoginThrottle(
        secret_key=(
            "unit-test-throttle-secret"
        ),
        ip_max_attempts=(
            ip_max_attempts
        ),
        ip_window_seconds=(
            ip_window_seconds
        ),
        account_max_failures=(
            account_max_failures
        ),
        account_window_seconds=(
            account_window_seconds
        ),
        clock=clock,
    )


def test_ip_bucket_allows_attempts_below_limit(
) -> None:
    clock = FakeClock()

    throttle = create_throttle(
        clock
    )

    first = throttle.begin_attempt(
        client_address="203.0.113.10",
        account_identifier=(
            "first@example.com"
        ),
    )

    second = throttle.begin_attempt(
        client_address="203.0.113.10",
        account_identifier=(
            "second@example.com"
        ),
    )

    third = throttle.begin_attempt(
        client_address="203.0.113.10",
        account_identifier=(
            "third@example.com"
        ),
    )

    assert first.allowed is True
    assert second.allowed is True
    assert third.allowed is True


def test_ip_bucket_blocks_across_different_accounts(
) -> None:
    clock = FakeClock()

    throttle = create_throttle(
        clock
    )

    for index in range(
        3
    ):
        decision = (
            throttle.begin_attempt(
                client_address=(
                    "203.0.113.10"
                ),
                account_identifier=(
                    f"user{index}@example.com"
                ),
            )
        )

        assert (
            decision.allowed
            is True
        )

    blocked = (
        throttle.begin_attempt(
            client_address=(
                "203.0.113.10"
            ),
            account_identifier=(
                "another@example.com"
            ),
        )
    )

    assert blocked.allowed is False

    assert (
        blocked.blocked_by
        == "ip"
    )


def test_account_bucket_blocks_across_different_ips(
) -> None:
    clock = FakeClock()

    throttle = create_throttle(
        clock,
        ip_max_attempts=100,
    )

    first = throttle.begin_attempt(
        client_address="203.0.113.1",
        account_identifier=(
            "victim@example.com"
        ),
    )

    assert first.allowed is True

    throttle.record_failure(
        account_identifier=(
            "victim@example.com"
        )
    )

    second = throttle.begin_attempt(
        client_address="203.0.113.2",
        account_identifier=(
            "victim@example.com"
        ),
    )

    assert second.allowed is True

    throttle.record_failure(
        account_identifier=(
            "victim@example.com"
        )
    )

    blocked = (
        throttle.begin_attempt(
            client_address=(
                "203.0.113.3"
            ),
            account_identifier=(
                "victim@example.com"
            ),
        )
    )

    assert blocked.allowed is False

    assert (
        blocked.blocked_by
        == "account"
    )


def test_account_identifier_is_normalized(
) -> None:
    clock = FakeClock()

    throttle = create_throttle(
        clock,
        ip_max_attempts=100,
    )

    first = throttle.begin_attempt(
        client_address="203.0.113.1",
        account_identifier=(
            "  USER@EXAMPLE.COM  "
        ),
    )

    assert first.allowed is True

    throttle.record_failure(
        account_identifier=(
            "  USER@EXAMPLE.COM  "
        )
    )

    second = throttle.begin_attempt(
        client_address="203.0.113.2",
        account_identifier=(
            "user@example.com"
        ),
    )

    assert second.allowed is True

    throttle.record_failure(
        account_identifier=(
            "user@example.com"
        )
    )

    blocked = (
        throttle.begin_attempt(
            client_address=(
                "203.0.113.3"
            ),
            account_identifier=(
                "USER@EXAMPLE.COM"
            ),
        )
    )

    assert blocked.allowed is False


def test_success_clears_account_failures(
) -> None:
    clock = FakeClock()

    throttle = create_throttle(
        clock,
        ip_max_attempts=100,
    )

    first = throttle.begin_attempt(
        client_address="203.0.113.1",
        account_identifier=(
            "user@example.com"
        ),
    )

    assert first.allowed is True

    throttle.record_failure(
        account_identifier=(
            "user@example.com"
        )
    )

    throttle.record_failure(
        account_identifier=(
            "user@example.com"
        )
    )

    throttle.record_success(
        account_identifier=(
            "user@example.com"
        )
    )

    next_attempt = (
        throttle.begin_attempt(
            client_address=(
                "203.0.113.2"
            ),
            account_identifier=(
                "user@example.com"
            ),
        )
    )

    assert (
        next_attempt.allowed
        is True
    )


def test_ip_window_expires(
) -> None:
    clock = FakeClock()

    throttle = create_throttle(
        clock,
        ip_max_attempts=2,
        ip_window_seconds=60,
    )

    throttle.begin_attempt(
        client_address="203.0.113.10",
        account_identifier="one@example.com",
    )

    throttle.begin_attempt(
        client_address="203.0.113.10",
        account_identifier="two@example.com",
    )

    blocked = throttle.begin_attempt(
        client_address="203.0.113.10",
        account_identifier="three@example.com",
    )

    assert blocked.allowed is False

    clock.advance(
        61
    )

    allowed_again = (
        throttle.begin_attempt(
            client_address=(
                "203.0.113.10"
            ),
            account_identifier=(
                "four@example.com"
            ),
        )
    )

    assert (
        allowed_again.allowed
        is True
    )


def test_account_failure_window_expires(
) -> None:
    clock = FakeClock()

    throttle = create_throttle(
        clock,
        ip_max_attempts=100,
        account_max_failures=2,
        account_window_seconds=300,
    )

    throttle.record_failure(
        account_identifier=(
            "user@example.com"
        )
    )

    throttle.record_failure(
        account_identifier=(
            "user@example.com"
        )
    )

    blocked = (
        throttle.begin_attempt(
            client_address=(
                "203.0.113.10"
            ),
            account_identifier=(
                "user@example.com"
            ),
        )
    )

    assert blocked.allowed is False

    clock.advance(
        301
    )

    allowed_again = (
        throttle.begin_attempt(
            client_address=(
                "203.0.113.11"
            ),
            account_identifier=(
                "user@example.com"
            ),
        )
    )

    assert (
        allowed_again.allowed
        is True
    )


def test_reset_clears_throttle_state(
) -> None:
    clock = FakeClock()

    throttle = create_throttle(
        clock,
        ip_max_attempts=1,
    )

    first = throttle.begin_attempt(
        client_address="203.0.113.10",
        account_identifier=(
            "user@example.com"
        ),
    )

    assert first.allowed is True

    blocked = throttle.begin_attempt(
        client_address="203.0.113.10",
        account_identifier=(
            "other@example.com"
        ),
    )

    assert blocked.allowed is False

    throttle.reset()

    allowed_again = (
        throttle.begin_attempt(
            client_address=(
                "203.0.113.10"
            ),
            account_identifier=(
                "other@example.com"
            ),
        )
    )

    assert (
        allowed_again.allowed
        is True
    )