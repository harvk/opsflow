# ==========================================================
# OPSFLOW FRONTEND DEVELOPMENT IMAGE
# ==========================================================
#
# Purpose:
#
#   Run the React + TypeScript + Vite frontend inside Docker
#   for the local OpsFlow development environment.
#
# This is intentionally a DEVELOPMENT image.
#
# Production static-file serving will be handled separately
# from this development containerization phase.
#
# ==========================================================


# ==========================================================
# NODE BASE IMAGE
# ==========================================================

ARG NODE_VERSION=24

FROM node:${NODE_VERSION}-bookworm-slim


# ==========================================================
# APPLICATION ENVIRONMENT
# ==========================================================
#
# Keep npm and frontend tooling in development mode.
#
# Vite and the TypeScript/build tooling are commonly stored
# under devDependencies, so those dependencies must remain
# installed.
#
# ==========================================================

ENV NODE_ENV=development


# ==========================================================
# WORKING DIRECTORY
# ==========================================================
#
# Everything below this point executes relative to:
#
#     /app
#
# Host:
#
#     ./frontend
#
# Container:
#
#     /app
#
# ==========================================================

WORKDIR /app


# ==========================================================
# DEPENDENCY MANIFESTS
# ==========================================================
#
# Copy dependency manifests separately from source code.
#
# This gives Docker an independent dependency cache layer.
#
# If neither file changes:
#
#     package.json
#     package-lock.json
#
# Docker can generally reuse the npm ci layer.
#
# ==========================================================

COPY package.json package-lock.json ./


# ==========================================================
# DEPENDENCY INSTALLATION
# ==========================================================
#
# npm ci installs the dependency graph recorded by the
# committed package-lock.json.
#
# The installation occurs inside Linux rather than copying
# host-installed Windows dependencies.
#
# ==========================================================

RUN npm ci


# ==========================================================
# APPLICATION SOURCE
# ==========================================================
#
# Copy the rest of the frontend source.
#
# frontend/.dockerignore controls files excluded from this
# build context.
#
# Runtime environment files are deliberately excluded.
#
# ==========================================================

COPY . .


# ==========================================================
# VITE DEVELOPMENT PORT
# ==========================================================
#
# EXPOSE documents the port used by the application inside
# the container.
#
# It does not publish the port to the Windows host.
#
# Docker run or Docker Compose performs that mapping.
#
# ==========================================================

EXPOSE 5173


# ==========================================================
# VITE DEVELOPMENT SERVER
# ==========================================================
#
# --host 0.0.0.0
#
#     Vite must listen beyond the container's localhost
#     interface so Docker port publishing can reach it.
#
#
# --port 5173
#
#     Use our defined frontend development port.
#
#
# --strictPort
#
#     Never silently move to 5174, 5175, etc.
#
#     Docker expects the application to remain on 5173.
#
# ==========================================================

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173", "--strictPort"]