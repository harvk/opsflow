# syntax=docker/dockerfile:1


# ==========================================================
# OPSFLOW INCIDENT SERVICE IMAGE
# ==========================================================
#
# Multi-stage image:
#
#   builder
#       creates an isolated virtual environment
#       installs runtime-only dependencies
#       validates dependency consistency
#       removes pip from the virtual environment
#
#   runtime
#       contains only the runtime environment and app source
#       executes as a non-root user
#       does not include tests or development tools
#
# ==========================================================


ARG PYTHON_VERSION=3.13.15


# ==========================================================
# STAGE 1 — RUNTIME DEPENDENCY BUILDER
# ==========================================================

FROM python:${PYTHON_VERSION}-slim-trixie AS builder


ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1


WORKDIR /build


RUN python -m venv /opt/venv


ENV PATH="/opt/venv/bin:${PATH}"


COPY requirements-runtime.txt ./requirements-runtime.txt


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


ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:${PATH}" \
    HOME="/home/incident"


# ----------------------------------------------------------
# REMOVE SYSTEM PIP FROM THE FINAL IMAGE
# ----------------------------------------------------------

RUN python -m pip uninstall --yes pip \
    && python -c \
        "import importlib.util; assert importlib.util.find_spec('pip') is None"


# ----------------------------------------------------------
# CREATE THE NON-ROOT RUNTIME IDENTITY
# ----------------------------------------------------------

RUN groupadd \
        --gid 10001 \
        incident \
    && useradd \
        --uid 10001 \
        --gid incident \
        --create-home \
        --shell /usr/sbin/nologin \
        incident


WORKDIR /app


# ----------------------------------------------------------
# COPY THE PREBUILT VIRTUAL ENVIRONMENT
# ----------------------------------------------------------

COPY --from=builder \
    --chown=root:root \
    /opt/venv \
    /opt/venv


# ----------------------------------------------------------
# COPY APPLICATION SOURCE
# ----------------------------------------------------------

COPY --chown=root:root \
    app \
    ./app


# ----------------------------------------------------------
# PROTECT DEPLOYED SOURCE FROM RUNTIME MODIFICATION
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

USER 10001:10001


EXPOSE 8000


CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]