# Build stage
FROM node:24.22.3-trixie-slim@sha256:af02d57b57719b9657a45199a79264a9437940cd55b3c7b3fc99615654f124a0 AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ARG VITE_SENTRY_DSN=""
ARG SENTRY_RELEASE=""
ENV VITE_SENTRY_DSN=${VITE_SENTRY_DSN}
ENV VITE_SENTRY_RELEASE=${SENTRY_RELEASE}
RUN npm run build

# Serve stage
FROM ghcr.io/nginx/nginx-unprivileged:1.31.9-trixie@sha256:0255fc1dcc1d7b358aac20166543e52029fea577413edadb0912f5b928c7e312
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 8080
