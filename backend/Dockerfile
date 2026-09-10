# syntax=docker/dockerfile:1


# ==========================================================
# OPSFLOW FASTAPI BACKEND IMAGE
# ==========================================================
#
# This is a multi-stage Docker build.
#
# Stage 1 installs Python dependencies.
#
# Stage 2 creates the smaller runtime image that actually
# executes FastAPI.
#
# The Python major/minor version can be supplied by
# Docker Compose using a build argument.
#
# ==========================================================


ARG PYTHON_VERSION=3.13


# ==========================================================
# STAGE 1 — DEPENDENCY BUILDER
# ==========================================================

FROM python:${PYTHON_VERSION}-slim-bookworm AS builder


# ----------------------------------------------------------
# PYTHON RUNTIME BEHAVIOR
# ----------------------------------------------------------
#
# PYTHONDONTWRITEBYTECODE=1
#
# Prevents Python from creating .pyc bytecode cache files.
#
#
# PYTHONUNBUFFERED=1
#
# Causes logs to be written directly to stdout/stderr.
# This is desirable in Docker because Docker captures those
# streams as container logs.
#
#
# PIP_DISABLE_PIP_VERSION_CHECK=1
#
# Suppresses pip's periodic version-check message.
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
# CREATE AN ISOLATED PYTHON VIRTUAL ENVIRONMENT
# ----------------------------------------------------------

RUN python -m venv /opt/venv


# ----------------------------------------------------------
# MAKE THAT VIRTUAL ENVIRONMENT THE DEFAULT PYTHON/PIP
# ----------------------------------------------------------

ENV PATH="/opt/venv/bin:${PATH}"


# ----------------------------------------------------------
# COPY ONLY REQUIREMENTS FIRST
# ----------------------------------------------------------
#
# This creates a Docker cache boundary.
#
# If Python source code changes but requirements.txt does
# not change, Docker can reuse the installed dependency
# layer rather than reinstalling everything.
#
# ----------------------------------------------------------

COPY requirements.txt ./requirements.txt


# ----------------------------------------------------------
# INSTALL PYTHON DEPENDENCIES
# ----------------------------------------------------------

RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --upgrade pip \
    && python -m pip install \
        --requirement requirements.txt


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
    PATH="/opt/venv/bin:${PATH}"


# ----------------------------------------------------------
# CREATE A NON-ROOT APPLICATION USER
# ----------------------------------------------------------
#
# Containers default to root unless told otherwise.
#
# Running FastAPI as root is unnecessary.
#
# We create:
#
#   user:  opsflow
#   UID:   10001
#   GID:   10001
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
# COPY THE PREBUILT PYTHON ENVIRONMENT
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
# Phase 8.4 will use these files.
#
# We include them now so the same backend image can later
# execute Alembic commands.
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
# DOCUMENT THE FASTAPI PORT
# ----------------------------------------------------------

EXPOSE 8000


# ----------------------------------------------------------
# START UVICORN
# ----------------------------------------------------------
#
# IMPORTANT:
#
# Keep this CMD instruction on ONE physical Dockerfile line.
#
# ----------------------------------------------------------

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]