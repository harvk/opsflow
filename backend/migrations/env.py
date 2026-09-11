import os

from logging.config import (
    fileConfig,
)

from alembic import (
    context,
)

from dotenv import (
    load_dotenv,
)

from sqlalchemy import (
    engine_from_config,
    pool,
)

from app.db.base_metadata import (
    Base,
)

from app.models.incident import (
    IncidentModel,
)

from app.models.service import (
    ServiceDependencyModel,
    ServiceModel,
)

from app.models.user import (
    UserModel,
)


# =========================================================
# LOCAL DEVELOPMENT ENVIRONMENT
# =========================================================
#
# Host-side development commonly runs Alembic from:
#
#     opsflow/backend
#
# where:
#
#     backend/.env
#
# contains DATABASE_URL.
#
# load_dotenv() supports that local workflow.
#
# Inside the Docker migration container there is deliberately
# no .env file. Docker Compose injects DATABASE_URL directly
# into the process environment instead.
#
# Existing process environment variables take precedence over
# values discovered in .env.
#
# =========================================================

load_dotenv(
    override=False,
)


# =========================================================
# ALEMBIC CONFIGURATION
# =========================================================

config = (
    context.config
)


# =========================================================
# DATABASE URL RESOLUTION
# =========================================================
#
# Alembic needs database configuration.
#
# It does NOT need the complete FastAPI Settings object.
#
# Importing:
#
#     app.core.config.settings
#
# would unnecessarily require application secrets such as:
#
#     JWT signing keys
#     CSRF signing material
#     throttle HMAC material
#     security-event HMAC material
#     password-reset configuration
#
# DATABASE_URL is therefore resolved directly from the
# process environment.
#
# In Docker:
#
#     Compose injects DATABASE_URL.
#
# During host development:
#
#     load_dotenv() can load backend/.env.
#
# =========================================================


def get_database_url(
) -> str:
    database_url = (
        os.environ
        .get(
            "DATABASE_URL",
            "",
        )
        .strip()
    )

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL must be set "
            "before Alembic can run."
        )

    return database_url


def escape_alembic_config_value(
    value: str,
) -> str:
    """
    Escape percent characters for the ConfigParser-backed
    Alembic configuration object.

    A percent character can legitimately appear in an
    encoded database credential. ConfigParser treats percent
    signs as interpolation syntax unless they are escaped.
    """

    return value.replace(
        "%",
        "%%",
    )


database_url = (
    get_database_url()
)

config.set_main_option(
    "sqlalchemy.url",
    escape_alembic_config_value(
        database_url
    ),
)


# =========================================================
# LOGGING
# =========================================================

if (
    config.config_file_name
    is not None
):
    fileConfig(
        config.config_file_name
    )


# =========================================================
# MODEL METADATA
# =========================================================
#
# Model imports above register their tables with Base.
#
# These imports are deliberately retained so Alembic
# autogenerate can compare all application models against
# the database schema.
#
# =========================================================

target_metadata = (
    Base.metadata
)


# =========================================================
# OFFLINE MIGRATIONS
# =========================================================


def run_migrations_offline(
) -> None:
    """
    Run Alembic migrations without creating an Engine.
    """

    url = (
        config
        .get_main_option(
            "sqlalchemy.url"
        )
    )

    context.configure(
        url=url,
        target_metadata=(
            target_metadata
        ),
        literal_binds=True,
        dialect_opts={
            "paramstyle": "named",
        },
    )

    with (
        context
        .begin_transaction()
    ):
        context.run_migrations()


# =========================================================
# ONLINE MIGRATIONS
# =========================================================


def run_migrations_online(
) -> None:
    """
    Run Alembic migrations using a live database Engine.
    """

    connectable = (
        engine_from_config(
            config.get_section(
                config.config_ini_section,
                {},
            ),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )
    )

    with (
        connectable.connect()
        as connection
    ):
        context.configure(
            connection=connection,
            target_metadata=(
                target_metadata
            ),
        )

        with (
            context
            .begin_transaction()
        ):
            context.run_migrations()


# =========================================================
# EXECUTION MODE
# =========================================================

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()