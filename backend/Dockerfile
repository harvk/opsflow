# syntax=docker/dockerfile:1


# ==========================================================
# OPSFLOW FASTAPI BACKEND IMAGE
# ==========================================================
#
# Multi-stage backend image.
#
# Stage 1:
#   - creates the Python virtual environment
#   - installs runtime-only Python dependencies
#   - validates installed dependency consistency
#   - removes pip after dependency installation
#
# Stage 2:
#   - starts from a clean Python runtime
#   - removes the base image's system pip
#   - contains the prebuilt virtual environment
#   - contains FastAPI application source
#   - contains Alembic migration source
#   - executes as an unprivileged application user
#
# Runtime package installation is intentionally disabled.
# Package-management tooling is a build-time concern, not a
# production runtime requirement for OpsFlow.
#
# Runtime application source remains owned by root so the
# unprivileged application process cannot modify its own
# deployed code.
#
# ==========================================================


ARG PYTHON_VERSION=3.13


# ==========================================================
# STAGE 1 — RUNTIME DEPENDENCY BUILDER
# ==========================================================

FROM python:${PYTHON_VERSION}-slim-trixie AS builder


# ----------------------------------------------------------
# PYTHON / PIP BUILD BEHAVIOR
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
# USE THE VIRTUAL ENVIRONMENT BY DEFAULT
# ----------------------------------------------------------

ENV PATH="/opt/venv/bin:${PATH}"


# ----------------------------------------------------------
# COPY RUNTIME DEPENDENCY MANIFEST
# ----------------------------------------------------------

COPY requirements-runtime.txt ./requirements-runtime.txt


# ----------------------------------------------------------
# INSTALL RUNTIME DEPENDENCIES
# ----------------------------------------------------------
#
# pip is required only while constructing the virtual
# environment.
#
# After installation:
#
#   1. pip check validates dependency consistency.
#   2. pip removes itself from /opt/venv.
#   3. Python verifies that the pip module is no longer
#      importable from the runtime virtual environment.
#
# This prevents pip's vendored libraries, including its
# vendored msgpack implementation, from being copied into
# the final runtime image.
#
# ----------------------------------------------------------

RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --upgrade pip \
    && python -m pip install \
        --no-compile \
        --requirement requirements-runtime.txt \
    && python -m pip check \
    && python -m pip uninstall --yes pip \
    && python -c \
        "import importlib.util; assert importlib.util.find_spec('pip') is None"


# ==========================================================
# STAGE 2 — RUNTIME IMAGE
# ==========================================================

FROM python:${PYTHON_VERSION}-slim-trixie AS runtime


# ----------------------------------------------------------
# RUNTIME ENVIRONMENT
# ----------------------------------------------------------
#
# PIP_DISABLE_PIP_VERSION_CHECK is intentionally absent.
#
# pip does not belong in the final OpsFlow runtime image.
#
# ----------------------------------------------------------

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:${PATH}" \
    HOME="/home/opsflow"


# ----------------------------------------------------------
# REMOVE BASE-IMAGE PACKAGE MANAGEMENT TOOLING
# ----------------------------------------------------------
#
# The official Python runtime image contains its own pip
# installation under /usr/local.
#
# OpsFlow does not install Python packages at runtime.
#
# Remove system pip before /opt/venv is copied into this
# stage.
#
# At this point /opt/venv does not yet exist, so "python"
# resolves to the runtime image's system interpreter.
#
# The verification command ensures that pip truly became
# unavailable instead of silently leaving an importable
# installation behind.
#
# ----------------------------------------------------------

RUN python -m pip uninstall --yes pip \
    && python -c \
        "import importlib.util; assert importlib.util.find_spec('pip') is None"


# ----------------------------------------------------------
# CREATE UNPRIVILEGED APPLICATION IDENTITY
# ----------------------------------------------------------
#
# The account receives a writable home directory but does
# not own the deployed application or virtual environment.
#
# UID/GID 10001 gives the runtime a stable non-root identity.
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
#
# WORKDIR is created by root and intentionally remains
# root-owned.
#
# ----------------------------------------------------------

WORKDIR /app


# ----------------------------------------------------------
# COPY PREBUILT PYTHON ENVIRONMENT
# ----------------------------------------------------------
#
# The virtual environment remains root-owned. The runtime
# user requires read/execute access only.
#
# pip has already been removed from this virtual environment
# in the builder stage.
#
# ----------------------------------------------------------

COPY --from=builder \
    --chown=root:root \
    /opt/venv \
    /opt/venv


# ----------------------------------------------------------
# COPY FASTAPI APPLICATION SOURCE
# ----------------------------------------------------------
#
# Application source is deliberately owned by root rather
# than by the account executing FastAPI.
#
# ----------------------------------------------------------

COPY --chown=root:root \
    app \
    ./app


# ----------------------------------------------------------
# COPY ALEMBIC MIGRATION SOURCE
# ----------------------------------------------------------

COPY --chown=root:root \
    migrations \
    ./migrations


# ----------------------------------------------------------
# COPY ALEMBIC CONFIGURATION
# ----------------------------------------------------------

COPY --chown=root:root \
    alembic.ini \
    ./alembic.ini


# ----------------------------------------------------------
# LOCK DEPLOYED APPLICATION FILES
# ----------------------------------------------------------
#
# Directories:
#   r-xr-xr-x  (0555)
#
# Files:
#   r--r--r--  (0444)
#
# FastAPI and Alembic only need to read/import these files.
# The application user should not modify deployed source.
#
# ----------------------------------------------------------

RUN find /app \
        -type d \
        -exec chmod 0555 {} + \
    && find /app \
        -type f \
        -exec chmod 0444 {} +


# ----------------------------------------------------------
# DROP ROOT PRIVILEGES
# ----------------------------------------------------------
#
# Numeric UID/GID makes the runtime identity explicit even
# if username resolution is not required by tooling.
#
# ----------------------------------------------------------

USER 10001:10001


# ----------------------------------------------------------
# DOCUMENT FASTAPI PORT
# ----------------------------------------------------------

EXPOSE 8000


# ----------------------------------------------------------
# START UVICORN
# ----------------------------------------------------------

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]