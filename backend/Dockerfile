# syntax=docker/dockerfile:1


# ==========================================================
# OPSFLOW FASTAPI BACKEND IMAGE
# ==========================================================
#
# This is a multi-stage Docker build.
#
# Stage 1 creates an isolated Python virtual environment and
# installs only dependencies required by the runtime image.
#
# Stage 2 contains only the Python runtime, the prebuilt
# virtual environment, application source, and Alembic
# migration files.
#
# Development and test tooling remains outside this image.
#
# The Python major/minor version can be supplied by Docker
# Compose using a build argument.
#
# ==========================================================


ARG PYTHON_VERSION=3.13


# ==========================================================
# STAGE 1 — RUNTIME DEPENDENCY BUILDER
# ==========================================================

FROM python:${PYTHON_VERSION}-slim-bookworm AS builder


# ----------------------------------------------------------
# PYTHON / PIP BUILD BEHAVIOR
# ----------------------------------------------------------
#
# PYTHONDONTWRITEBYTECODE=1
#
# Prevents Python from creating .pyc bytecode cache files
# while Python code executes during the image build.
#
#
# PYTHONUNBUFFERED=1
#
# Causes Python output to be written directly to
# stdout/stderr.
#
#
# PIP_DISABLE_PIP_VERSION_CHECK=1
#
# Prevents unnecessary pip version-check traffic/output.
#
# ----------------------------------------------------------

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1


# ----------------------------------------------------------
# BUILD WORKING DIRECTORY
# ----------------------------------------------------------

WORKDIR /build


# ----------------------------------------------------------
# CREATE ISOLATED RUNTIME VIRTUAL ENVIRONMENT
# ----------------------------------------------------------

RUN python -m venv /opt/venv


# ----------------------------------------------------------
# MAKE THE VIRTUAL ENVIRONMENT THE DEFAULT PYTHON/PIP
# ----------------------------------------------------------

ENV PATH="/opt/venv/bin:${PATH}"


# ----------------------------------------------------------
# COPY ONLY THE RUNTIME DEPENDENCY MANIFEST
# ----------------------------------------------------------
#
# requirements.txt remains the complete development/test
# dependency manifest used outside the production-style
# runtime image.
#
# requirements-runtime.txt intentionally excludes packages
# that are needed only for testing, linting, development
# reload behavior, or other non-runtime workflows.
#
# Keeping this COPY before application source also preserves
# Docker's dependency-layer cache boundary.
#
# ----------------------------------------------------------

COPY requirements-runtime.txt ./requirements-runtime.txt


# ----------------------------------------------------------
# INSTALL RUNTIME DEPENDENCIES
# ----------------------------------------------------------
#
# The BuildKit cache mount accelerates later builds without
# copying pip's download cache into the final runtime image.
#
# --no-compile prevents pip from generating Python bytecode
# during installation. Runtime bytecode writes are also
# disabled by PYTHONDONTWRITEBYTECODE.
#
# ----------------------------------------------------------

RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --upgrade pip \
    && python -m pip install \
        --no-compile \
        --requirement requirements-runtime.txt


# ==========================================================
# STAGE 2 — RUNTIME IMAGE
# ==========================================================

FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime


# ----------------------------------------------------------
# RUNTIME ENVIRONMENT
# ----------------------------------------------------------

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH="/opt/venv/bin:${PATH}" \
    HOME="/home/opsflow"


# ----------------------------------------------------------
# CREATE NON-ROOT APPLICATION USER
# ----------------------------------------------------------
#
# The backend does not require root privileges.
#
# UID/GID 10001 provides a stable application identity that
# does not overlap with the usual low-numbered system users.
#
# The login shell is disabled.
#
# ----------------------------------------------------------

RUN groupadd \
        --gid 10001 \
        opsflow \
    && useradd \
        --uid 10001 \
        --gid opsflow \
        --create-home \
        --shell /usr/sbin/nologin \
        opsflow


# ----------------------------------------------------------
# APPLICATION WORKING DIRECTORY
# ----------------------------------------------------------

WORKDIR /app


# ----------------------------------------------------------
# COPY PREBUILT RUNTIME PYTHON ENVIRONMENT
# ----------------------------------------------------------

COPY --from=builder \
    /opt/venv \
    /opt/venv


# ----------------------------------------------------------
# COPY FASTAPI APPLICATION SOURCE
# ----------------------------------------------------------

COPY --chown=opsflow:opsflow \
    app \
    ./app


# ----------------------------------------------------------
# COPY ALEMBIC MIGRATIONS
# ----------------------------------------------------------
#
# The same backend image is used by the one-shot Compose
# migration service, so Alembic migration source must remain
# available in the runtime image.
#
# ----------------------------------------------------------

COPY --chown=opsflow:opsflow \
    migrations \
    ./migrations


# ----------------------------------------------------------
# COPY ALEMBIC CONFIGURATION
# ----------------------------------------------------------

COPY --chown=opsflow:opsflow \
    alembic.ini \
    ./alembic.ini


# ----------------------------------------------------------
# DROP ROOT PRIVILEGES
# ----------------------------------------------------------

USER opsflow


# ----------------------------------------------------------
# DOCUMENT FASTAPI PORT
# ----------------------------------------------------------

EXPOSE 8000


# ----------------------------------------------------------
# START UVICORN
# ----------------------------------------------------------
#
# Development reload is intentionally not enabled.
#
# ----------------------------------------------------------

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]