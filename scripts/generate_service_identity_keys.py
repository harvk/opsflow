from __future__ import annotations

import argparse
import hashlib
from pathlib import (
    Path,
)

from cryptography.hazmat.primitives.asymmetric import (
    rsa,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

DEFAULT_OUTPUT_DIRECTORY = Path(
    ".opsflow-secrets"
)

PRIVATE_KEY_FILENAME = (
    "core-service-identity-private.pem"
)

PUBLIC_KEY_FILENAME = (
    "core-service-identity-public.pem"
)

RSA_KEY_SIZE = 2048


def parse_arguments(
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate the local-development RSA keypair "
            "used by the OpsFlow Core Backend service "
            "identity. Existing keys are never overwritten."
        )
    )

    parser.add_argument(
        "--output-directory",
        type=Path,
        default=(
            DEFAULT_OUTPUT_DIRECTORY
        ),
        help=(
            "Directory that receives the private and "
            "public PEM files."
        ),
    )

    return parser.parse_args()


def write_new_file(
    path: Path,
    content: bytes,
    *,
    mode: int,
) -> None:
    with path.open(
        "xb"
    ) as output_file:
        output_file.write(
            content
        )

    path.chmod(
        mode
    )


def main(
) -> None:
    arguments = parse_arguments()

    output_directory = (
        arguments
        .output_directory
        .expanduser()
        .resolve()
    )

    private_key_path = (
        output_directory
        / PRIVATE_KEY_FILENAME
    )

    public_key_path = (
        output_directory
        / PUBLIC_KEY_FILENAME
    )

    existing_paths = [
        path
        for path in (
            private_key_path,
            public_key_path,
        )
        if path.exists()
    ]

    if existing_paths:
        existing_names = ", ".join(
            path.name
            for path in existing_paths
        )

        raise SystemExit(
            "Refusing to overwrite existing service "
            f"identity file(s): {existing_names}"
        )

    output_directory.mkdir(
        mode=0o700,
        parents=True,
        exist_ok=True,
    )

    private_key = (
        rsa.generate_private_key(
            public_exponent=65537,
            key_size=RSA_KEY_SIZE,
        )
    )

    private_key_pem = (
        private_key.private_bytes(
            encoding=Encoding.PEM,
            format=(
                PrivateFormat.PKCS8
            ),
            encryption_algorithm=(
                NoEncryption()
            ),
        )
    )

    public_key_pem = (
        private_key
        .public_key()
        .public_bytes(
            encoding=Encoding.PEM,
            format=(
                PublicFormat.SubjectPublicKeyInfo
            ),
        )
    )

    write_new_file(
        private_key_path,
        private_key_pem,
        mode=0o600,
    )

    write_new_file(
        public_key_path,
        public_key_pem,
        mode=0o644,
    )

    public_key_fingerprint = (
        hashlib.sha256(
            public_key_pem
        )
        .hexdigest()
    )

    print(
        "Generated Core service-identity keypair."
    )
    print(
        f"Private key: {private_key_path}"
    )
    print(
        f"Public key:  {public_key_path}"
    )
    print(
        "Public-key SHA-256 fingerprint: "
        f"{public_key_fingerprint}"
    )


if __name__ == "__main__":
    main()
