from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)

from app.repositories.auth_session_repository import (
    AuthSessionRepository,
)


class AuthSessionMaintenanceService:
    """
    Maintenance operations for persistent authentication
    sessions.

    This service is intentionally separate from
    AuthenticationService.

    AuthenticationService handles live authentication.

    AuthSessionMaintenanceService handles lifecycle cleanup
    that may later run from a scheduled AWS task.
    """

    def __init__(
        self,
        repository: AuthSessionRepository,
        *,
        retention_days: int,
    ) -> None:
        if (
            retention_days
            < 1
        ):
            raise ValueError(
                "Authentication-session retention "
                "must be at least one day."
            )

        self.repository = repository

        self.retention_days = (
            retention_days
        )

    def purge_expired_sessions(
        self,
        *,
        now: datetime | None = None,
    ) -> int:
        """
        Delete session rows only after:

            session.expires_at
                +
            configured retention period

        has elapsed.
        """

        effective_now = (
            now
            if now is not None
            else datetime.now(
                timezone.utc
            )
        )

        if (
            effective_now.tzinfo
            is None
        ):
            raise ValueError(
                "Session-maintenance time "
                "must be timezone-aware."
            )

        cutoff = (
            effective_now
            - timedelta(
                days=(
                    self.retention_days
                )
            )
        )

        return (
            self.repository
            .delete_expired_before(
                cutoff=cutoff
            )
        )