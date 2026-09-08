from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)

from uuid import (
    uuid4,
)

import pytest

from sqlalchemy.orm import (
    Session,
)

from app.core.password_reset_tokens import (
    create_password_reset_credential_fingerprint,
    digest_password_reset_token,
    generate_password_reset_token,
)

from app.core.security import (
    hash_password,
    verify_password,
)

from app.domain.auth_session import (
    AuthSession,
)

from app.domain.password_reset_token import (
    PasswordResetToken,
)

from app.repositories.sqlalchemy_auth_session_repository import (
    SqlAlchemyAuthSessionRepository,
)

from app.repositories.sqlalchemy_password_reset_token_repository import (
    SqlAlchemyPasswordResetTokenRepository,
)

from app.repositories.sqlalchemy_user_repository import (
    SqlAlchemyUserRepository,
)

from app.services.password_reset_service import (
    InvalidPasswordResetCredentialError,
    PasswordResetPasswordError,
    PasswordResetService,
)

from app.services.user_service import (
    UserService,
)


OLD_PASSWORD = (
    "VerySecurePassword123!"
)

NEW_PASSWORD = (
    "EvenMoreSecurePassword456!"
)


# =========================================================
# HELPERS
# =========================================================


def build_password_reset_service(
    db_session: Session,
) -> tuple[
    PasswordResetService,
    SqlAlchemyUserRepository,
    SqlAlchemyPasswordResetTokenRepository,
    SqlAlchemyAuthSessionRepository,
]:
    user_repository = (
        SqlAlchemyUserRepository(
            db_session
        )
    )

    reset_token_repository = (
        SqlAlchemyPasswordResetTokenRepository(
            db_session
        )
    )

    auth_session_repository = (
        SqlAlchemyAuthSessionRepository(
            db_session
        )
    )

    service = (
        PasswordResetService(
            user_repository=(
                user_repository
            ),
            password_reset_repository=(
                reset_token_repository
            ),
            auth_session_repository=(
                auth_session_repository
            ),
        )
    )

    return (
        service,
        user_repository,
        reset_token_repository,
        auth_session_repository,
    )


def create_test_user(
    user_repository: (
        SqlAlchemyUserRepository
    ),
):
    user_service = (
        UserService(
            user_repository
        )
    )

    return user_service.create_user(
        email=(
            f"password-reset-"
            f"{uuid4().hex}"
            "@example.com"
        ),
        full_name=(
            "Password Reset Test User"
        ),
        password=(
            OLD_PASSWORD
        ),
    )


def create_auth_session(
    *,
    user_id,
    auth_session_repository: (
        SqlAlchemyAuthSessionRepository
    ),
) -> AuthSession:
    now = datetime.now(
        timezone.utc
    )

    auth_session = (
        AuthSession(
            id=(
                uuid4()
            ),
            user_id=(
                user_id
            ),
            current_jti=(
                uuid4()
            ),
            created_at=(
                now
            ),
            last_used_at=(
                now
            ),
            expires_at=(
                now
                + timedelta(
                    days=7
                )
            ),
            revoked_at=None,
            revocation_reason=None,
        )
    )

    return (
        auth_session_repository
        .create(
            auth_session
        )
    )


# =========================================================
# ISSUANCE
# =========================================================


def test_password_reset_request_creates_persistent_digest(
    db_session: Session,
) -> None:
    (
        service,
        user_repository,
        reset_token_repository,
        _,
    ) = build_password_reset_service(
        db_session
    )

    user = create_test_user(
        user_repository
    )

    issuance = (
        service
        .request_reset(
            email=(
                user.email
            )
        )
    )

    assert (
        issuance
        is not None
    )

    digest = (
        digest_password_reset_token(
            issuance.raw_token
        )
    )

    persisted = (
        reset_token_repository
        .get_by_digest_for_update(
            digest
        )
    )

    assert (
        persisted
        is not None
    )

    assert (
        persisted.user_id
        == user.id
    )

    assert (
        persisted.token_digest
        == digest
    )

    # The database stores the digest, never the raw bearer
    # credential.
    assert (
        persisted.token_digest
        != issuance.raw_token
    )

    assert (
        persisted.used_at
        is None
    )

    assert (
        persisted.invalidated_at
        is None
    )


def test_unknown_email_does_not_create_reset_credential(
    db_session: Session,
) -> None:
    (
        service,
        _,
        _,
        _,
    ) = build_password_reset_service(
        db_session
    )

    issuance = (
        service
        .request_reset(
            email=(
                "missing-account@example.com"
            )
        )
    )

    assert (
        issuance
        is None
    )


def test_second_reset_request_invalidates_first_token(
    db_session: Session,
) -> None:
    (
        service,
        user_repository,
        reset_token_repository,
        _,
    ) = build_password_reset_service(
        db_session
    )

    user = create_test_user(
        user_repository
    )

    first = (
        service
        .request_reset(
            email=user.email
        )
    )

    assert (
        first
        is not None
    )

    second = (
        service
        .request_reset(
            email=user.email
        )
    )

    assert (
        second
        is not None
    )

    first_digest = (
        digest_password_reset_token(
            first.raw_token
        )
    )

    first_record = (
        reset_token_repository
        .get_by_digest_for_update(
            first_digest
        )
    )

    assert (
        first_record
        is not None
    )

    assert (
        first_record.invalidated_at
        is not None
    )

    second_digest = (
        digest_password_reset_token(
            second.raw_token
        )
    )

    second_record = (
        reset_token_repository
        .get_by_digest_for_update(
            second_digest
        )
    )

    assert (
        second_record
        is not None
    )

    assert (
        second_record.invalidated_at
        is None
    )


# =========================================================
# TOKEN VALIDATION
# =========================================================


def test_invalid_password_reset_token_is_rejected(
    db_session: Session,
) -> None:
    (
        service,
        _,
        _,
        _,
    ) = build_password_reset_service(
        db_session
    )

    with pytest.raises(
        InvalidPasswordResetCredentialError
    ):
        service.confirm_reset(
            raw_token=(
                generate_password_reset_token()
            ),
            new_password=(
                NEW_PASSWORD
            ),
        )


def test_expired_password_reset_token_is_rejected(
    db_session: Session,
) -> None:
    (
        service,
        user_repository,
        reset_token_repository,
        _,
    ) = build_password_reset_service(
        db_session
    )

    user = create_test_user(
        user_repository
    )

    auth_record = (
        user_repository
        .get_auth_record_by_email(
            user.email
        )
    )

    assert (
        auth_record
        is not None
    )

    raw_token = (
        generate_password_reset_token()
    )

    now = datetime.now(
        timezone.utc
    )

    reset_token_repository.create(
        PasswordResetToken(
            id=(
                uuid4()
            ),
            user_id=(
                user.id
            ),
            token_digest=(
                digest_password_reset_token(
                    raw_token
                )
            ),
            credential_fingerprint=(
                create_password_reset_credential_fingerprint(
                    auth_record
                    .hashed_password
                )
            ),
            created_at=(
                now
                - timedelta(
                    hours=1
                )
            ),
            expires_at=(
                now
                - timedelta(
                    seconds=1
                )
            ),
            used_at=None,
            invalidated_at=None,
        )
    )

    with pytest.raises(
        InvalidPasswordResetCredentialError
    ):
        service.confirm_reset(
            raw_token=(
                raw_token
            ),
            new_password=(
                NEW_PASSWORD
            ),
        )


# =========================================================
# PASSWORD POLICY
# =========================================================


def test_reset_rejects_short_password(
    db_session: Session,
) -> None:
    (
        service,
        user_repository,
        _,
        _,
    ) = build_password_reset_service(
        db_session
    )

    user = create_test_user(
        user_repository
    )

    issuance = (
        service
        .request_reset(
            email=user.email
        )
    )

    assert (
        issuance
        is not None
    )

    with pytest.raises(
        PasswordResetPasswordError
    ):
        service.confirm_reset(
            raw_token=(
                issuance.raw_token
            ),
            new_password=(
                "TooShort123!"
            ),
        )


def test_reset_rejects_current_password_reuse(
    db_session: Session,
) -> None:
    (
        service,
        user_repository,
        _,
        _,
    ) = build_password_reset_service(
        db_session
    )

    user = create_test_user(
        user_repository
    )

    issuance = (
        service
        .request_reset(
            email=user.email
        )
    )

    assert (
        issuance
        is not None
    )

    with pytest.raises(
        PasswordResetPasswordError
    ):
        service.confirm_reset(
            raw_token=(
                issuance.raw_token
            ),
            new_password=(
                OLD_PASSWORD
            ),
        )


# =========================================================
# SUCCESSFUL RESET
# =========================================================


def test_password_reset_changes_password(
    db_session: Session,
) -> None:
    (
        service,
        user_repository,
        _,
        _,
    ) = build_password_reset_service(
        db_session
    )

    user = create_test_user(
        user_repository
    )

    issuance = (
        service
        .request_reset(
            email=user.email
        )
    )

    assert (
        issuance
        is not None
    )

    result = (
        service
        .confirm_reset(
            raw_token=(
                issuance.raw_token
            ),
            new_password=(
                NEW_PASSWORD
            ),
        )
    )

    assert (
        result.user_id
        == user.id
    )

    # Bulk compare-and-set updates are used by the user
    # repository. Expire the test identity map before
    # reading the credential again.
    db_session.expire_all()

    auth_record = (
        user_repository
        .get_auth_record_by_email(
            user.email
        )
    )

    assert (
        auth_record
        is not None
    )

    assert verify_password(
        NEW_PASSWORD,
        auth_record.hashed_password,
    )

    assert not verify_password(
        OLD_PASSWORD,
        auth_record.hashed_password,
    )


def test_password_reset_token_is_single_use(
    db_session: Session,
) -> None:
    (
        service,
        user_repository,
        _,
        _,
    ) = build_password_reset_service(
        db_session
    )

    user = create_test_user(
        user_repository
    )

    issuance = (
        service
        .request_reset(
            email=user.email
        )
    )

    assert (
        issuance
        is not None
    )

    service.confirm_reset(
        raw_token=(
            issuance.raw_token
        ),
        new_password=(
            NEW_PASSWORD
        ),
    )

    db_session.expire_all()

    with pytest.raises(
        InvalidPasswordResetCredentialError
    ):
        service.confirm_reset(
            raw_token=(
                issuance.raw_token
            ),
            new_password=(
                "AnotherSecurePassword789!"
            ),
        )


def test_password_reset_revokes_existing_auth_sessions(
    db_session: Session,
) -> None:
    (
        service,
        user_repository,
        _,
        auth_session_repository,
    ) = build_password_reset_service(
        db_session
    )

    user = create_test_user(
        user_repository
    )

    first_session = (
        create_auth_session(
            user_id=(
                user.id
            ),
            auth_session_repository=(
                auth_session_repository
            ),
        )
    )

    second_session = (
        create_auth_session(
            user_id=(
                user.id
            ),
            auth_session_repository=(
                auth_session_repository
            ),
        )
    )

    issuance = (
        service
        .request_reset(
            email=user.email
        )
    )

    assert (
        issuance
        is not None
    )

    result = (
        service
        .confirm_reset(
            raw_token=(
                issuance.raw_token
            ),
            new_password=(
                NEW_PASSWORD
            ),
        )
    )

    assert (
        result.revoked_sessions
        == 2
    )

    db_session.expire_all()

    persisted_first = (
        auth_session_repository
        .get_by_id(
            first_session.id
        )
    )

    persisted_second = (
        auth_session_repository
        .get_by_id(
            second_session.id
        )
    )

    assert (
        persisted_first
        is not None
    )

    assert (
        persisted_second
        is not None
    )

    assert (
        persisted_first.revoked_at
        is not None
    )

    assert (
        persisted_second.revoked_at
        is not None
    )

    assert (
        persisted_first.revocation_reason
        == "password_reset"
    )

    assert (
        persisted_second.revocation_reason
        == "password_reset"
    )


# =========================================================
# CREDENTIAL VERSION BINDING
# =========================================================


def test_reset_token_becomes_stale_after_password_changes(
    db_session: Session,
) -> None:
    (
        service,
        user_repository,
        _,
        _,
    ) = build_password_reset_service(
        db_session
    )

    user = create_test_user(
        user_repository
    )

    issuance = (
        service
        .request_reset(
            email=user.email
        )
    )

    assert (
        issuance
        is not None
    )

    auth_record = (
        user_repository
        .get_auth_record_by_email(
            user.email
        )
    )

    assert (
        auth_record
        is not None
    )

    changed_elsewhere_hash = (
        hash_password(
            "ChangedElsewherePassword987!"
        )
    )

    changed = (
        user_repository
        .update_password_hash_if_current(
            user_id=(
                user.id
            ),
            expected_hashed_password=(
                auth_record
                .hashed_password
            ),
            new_hashed_password=(
                changed_elsewhere_hash
            ),
        )
    )

    assert (
        changed
        is True
    )

    db_session.expire_all()

    with pytest.raises(
        InvalidPasswordResetCredentialError
    ):
        service.confirm_reset(
            raw_token=(
                issuance.raw_token
            ),
            new_password=(
                NEW_PASSWORD
            ),
        )