from __future__ import annotations

from pathlib import (
    Path,
)

import pytest
from cryptography.hazmat.primitives import (
    serialization,
)
from cryptography.hazmat.primitives.asymmetric import (
    rsa,
)
from pydantic import (
    ValidationError,
)

from app.core.config import (
    Settings,
)
from app.core.service_identity import (
    JwtServiceTokenVerifier,
    ServiceIdentityConfigurationError,
)
from app.core.service_identity_loader import (
    build_service_token_verifier,
    load_service_verification_keys,
)


def write_public_key(
    key_file: Path,
) -> str:
    private_key = (
        rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
    )

    public_key_pem = (
        private_key
        .public_key()
        .public_bytes(
            encoding=(
                serialization
                .Encoding
                .PEM
            ),
            format=(
                serialization
                .PublicFormat
                .SubjectPublicKeyInfo
            ),
        )
        .decode(
            "utf-8"
        )
    )

    key_file.write_text(
        public_key_pem,
        encoding="utf-8",
    )

    return public_key_pem


def build_settings(
    public_key_file: Path,
    **overrides: object,
) -> Settings:
    values: dict[
        str,
        object,
    ] = {
        "database_url": (
            "postgresql+psycopg://test:test@db/test"
        ),
        "core_backend_url": (
            "http://backend:8000/api/v1"
        ),
        "service_identity_key_id": (
            "core-current"
        ),
        "service_identity_public_key_file": (
            public_key_file
        ),
    }

    values.update(
        overrides
    )

    return Settings.model_validate(
        values
    )


def test_loads_current_public_key(
    tmp_path: Path,
) -> None:
    key_file = (
        tmp_path
        / "current-public.pem"
    )

    expected_pem = write_public_key(
        key_file
    )

    keys = load_service_verification_keys(
        build_settings(
            key_file
        )
    )

    assert keys == {
        "core-current": expected_pem
    }


def test_loads_current_and_previous_public_keys(
    tmp_path: Path,
) -> None:
    current_key_file = (
        tmp_path
        / "current-public.pem"
    )

    previous_key_file = (
        tmp_path
        / "previous-public.pem"
    )

    current_pem = write_public_key(
        current_key_file
    )

    previous_pem = write_public_key(
        previous_key_file
    )

    keys = load_service_verification_keys(
        build_settings(
            current_key_file,
            service_identity_previous_key_id=(
                "core-previous"
            ),
            service_identity_previous_public_key_file=(
                previous_key_file
            ),
        )
    )

    assert keys == {
        "core-current": current_pem,
        "core-previous": previous_pem,
    }


@pytest.mark.parametrize(
    (
        "previous_key_id",
        "previous_key_file",
    ),
    [
        (
            "core-previous",
            None,
        ),
        (
            None,
            Path(
                "previous-public.pem"
            ),
        ),
    ],
)
def test_rejects_incomplete_previous_key_configuration(
    tmp_path: Path,
    previous_key_id: str | None,
    previous_key_file: Path | None,
) -> None:
    current_key_file = (
        tmp_path
        / "current-public.pem"
    )

    write_public_key(
        current_key_file
    )

    with pytest.raises(
        ValidationError,
        match=(
            "must be configured together"
        ),
    ):
        build_settings(
            current_key_file,
            service_identity_previous_key_id=(
                previous_key_id
            ),
            service_identity_previous_public_key_file=(
                previous_key_file
            ),
        )


def test_rejects_duplicate_rotation_key_ids(
    tmp_path: Path,
) -> None:
    current_key_file = (
        tmp_path
        / "current-public.pem"
    )

    previous_key_file = (
        tmp_path
        / "previous-public.pem"
    )

    write_public_key(
        current_key_file
    )

    write_public_key(
        previous_key_file
    )

    app_settings = build_settings(
        current_key_file,
        service_identity_previous_key_id=(
            "core-current"
        ),
        service_identity_previous_public_key_file=(
            previous_key_file
        ),
    )

    with pytest.raises(
        ServiceIdentityConfigurationError,
        match=(
            "key IDs must be different"
        ),
    ):
        load_service_verification_keys(
            app_settings
        )


def test_rejects_missing_current_public_key_file(
    tmp_path: Path,
) -> None:
    missing_key_file = (
        tmp_path
        / "missing-public.pem"
    )

    with pytest.raises(
        ServiceIdentityConfigurationError,
        match=(
            "SERVICE_IDENTITY_PUBLIC_KEY_FILE "
            "could not be read"
        ),
    ) as exc_info:
        load_service_verification_keys(
            build_settings(
                missing_key_file
            )
        )

    assert str(
        missing_key_file
    ) not in str(
        exc_info.value
    )


def test_rejects_empty_current_public_key_file(
    tmp_path: Path,
) -> None:
    empty_key_file = (
        tmp_path
        / "empty-public.pem"
    )

    empty_key_file.write_text(
        "   \n",
        encoding="utf-8",
    )

    with pytest.raises(
        ServiceIdentityConfigurationError,
        match=(
            "SERVICE_IDENTITY_PUBLIC_KEY_FILE "
            "must not be empty"
        ),
    ):
        load_service_verification_keys(
            build_settings(
                empty_key_file
            )
        )


def test_verifier_factory_rejects_invalid_pem(
    tmp_path: Path,
) -> None:
    invalid_key_file = (
        tmp_path
        / "invalid-public.pem"
    )

    invalid_key_file.write_text(
        "not a public key",
        encoding="utf-8",
    )

    with pytest.raises(
        ServiceIdentityConfigurationError,
        match=(
            "not a valid PEM public key"
        ),
    ):
        build_service_token_verifier(
            build_settings(
                invalid_key_file
            )
        )


def test_verifier_factory_builds_rs256_verifier(
    tmp_path: Path,
) -> None:
    key_file = (
        tmp_path
        / "current-public.pem"
    )

    write_public_key(
        key_file
    )

    verifier = build_service_token_verifier(
        build_settings(
            key_file,
            service_identity_clock_skew_seconds=10,
        )
    )

    assert isinstance(
        verifier,
        JwtServiceTokenVerifier,
    )
