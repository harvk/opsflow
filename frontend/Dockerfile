# syntax=docker/dockerfile:1


# ==========================================================
# OPSFLOW FRONTEND PRODUCTION IMAGE
# ==========================================================
#
# This is a multi-stage frontend build.
#
# Stage 1:
#
#     Node.js
#         |
#         +--> npm ci
#         |
#         +--> TypeScript compilation
#         |
#         +--> Vite production build
#         |
#         v
#       /app/dist
#
#
# Stage 2:
#
#     Unprivileged NGINX
#         |
#         +--> compiled static files only
#         |
#         v
#       port 8080
#
#
# Node.js, npm, TypeScript, Vite, source files, tests, and
# node_modules do NOT enter the final runtime image.
#
# ==========================================================


# ==========================================================
# GLOBAL BUILD ARGUMENTS
# ==========================================================

ARG NODE_VERSION=24


# ==========================================================
# STAGE 1 — FRONTEND BUILDER
# ==========================================================

FROM node:${NODE_VERSION}-bookworm-slim AS builder


# ----------------------------------------------------------
# BUILD WORKING DIRECTORY
# ----------------------------------------------------------

WORKDIR /app


# ----------------------------------------------------------
# DEPENDENCY MANIFESTS
# ----------------------------------------------------------
#
# Copy these independently from application source so Docker
# can preserve the npm dependency layer when source files
# change without package manifests changing.
#
# ----------------------------------------------------------

COPY package.json package-lock.json ./


# ----------------------------------------------------------
# INSTALL LOCKED DEPENDENCIES
# ----------------------------------------------------------
#
# Development dependencies are intentionally installed here.
#
# TypeScript, Vite, and the React Vite plugin are build tools
# and therefore required during this builder stage.
#
# They will not exist in the final NGINX image.
#
# ----------------------------------------------------------

RUN --mount=type=cache,target=/root/.npm \
    npm ci


# ----------------------------------------------------------
# COPY FRONTEND SOURCE
# ----------------------------------------------------------

COPY . .


# ----------------------------------------------------------
# BROWSER-VISIBLE BUILD CONFIGURATION
# ----------------------------------------------------------
#
# VITE_* values are embedded into the browser bundle during:
#
#     npm run build
#
# They are NOT runtime environment variables in the final
# NGINX container.
#
# Never use these arguments for private credentials.
#
# ----------------------------------------------------------

ARG VITE_API_BASE_URL=http://localhost:8000/api/v1
ARG VITE_CSRF_COOKIE_NAME=opsflow_csrf


# ----------------------------------------------------------
# BUILD PRODUCTION STATIC ASSETS
# ----------------------------------------------------------

RUN VITE_API_BASE_URL="${VITE_API_BASE_URL}" \
    VITE_CSRF_COOKIE_NAME="${VITE_CSRF_COOKIE_NAME}" \
    npm run build


# ==========================================================
# STAGE 2 — STATIC RUNTIME
# ==========================================================
#
# NGINX's unprivileged image is designed to operate without
# root privileges and uses non-privileged port 8080.
#
# ==========================================================

FROM nginxinc/nginx-unprivileged:stable-alpine AS runtime


# ----------------------------------------------------------
# REPLACE DEFAULT SITE CONFIGURATION
# ----------------------------------------------------------

COPY nginx/default.conf \
    /etc/nginx/conf.d/default.conf


# ----------------------------------------------------------
# COPY ONLY COMPILED FRONTEND ARTIFACTS
# ----------------------------------------------------------
#
# Nothing from:
#
#     src/
#     node_modules/
#     tests/
#     TypeScript tooling
#
# is copied into this runtime stage.
#
# ----------------------------------------------------------

COPY --from=builder \
    /app/dist \
    /usr/share/nginx/html


# ----------------------------------------------------------
# DOCUMENT RUNTIME PORT
# ----------------------------------------------------------

EXPOSE 8080


# ----------------------------------------------------------
# NGINX RUNTIME
# ----------------------------------------------------------
#
# The base image already defines the appropriate
# unprivileged execution identity and NGINX entrypoint.
#
# No development server command is required here.
#
# ----------------------------------------------------------

CMD ["nginx", "-g", "daemon off;"]