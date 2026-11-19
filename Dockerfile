# syntax=docker/dockerfile:1
# datasteg articles: Next.js standalone server, built from this folder (the newsroom pipeline is not in the image).
#
# The build stage runs on the machine's own platform (BUILDPLATFORM), so Next.js compiles at native speed; its output
# is plain JavaScript, which the runtime stage (TARGETPLATFORM) copies as is.
# `pnpm build` reads content/ (approved articles only: the build fails on an unapproved one).

FROM --platform=$BUILDPLATFORM node:24.22.0-alpine AS build
WORKDIR /repo
RUN npm install -g pnpm@11.18.0 >/dev/null
COPY pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm fetch
COPY . .
RUN pnpm install --offline --frozen-lockfile
ARG APP_VERSION=dev
ENV APP_VERSION=$APP_VERSION NEXT_TELEMETRY_DISABLED=1
RUN BUILD_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ) pnpm build

FROM node:24.22.0-alpine
WORKDIR /app
ARG APP_VERSION=dev
ENV NODE_ENV=production PORT=8080 HOSTNAME=0.0.0.0 NEXT_TELEMETRY_DISABLED=1 APP_VERSION=$APP_VERSION
COPY --from=build /repo/apps/web/.next/standalone ./
COPY --from=build /repo/apps/web/.next/static ./apps/web/.next/static
COPY --from=build /repo/apps/web/public ./apps/web/public
# Any non-root UID works. wget (busybox) serves the healthcheck.
USER 10050:10050
EXPOSE 8080
CMD ["node", "apps/web/server.js"]
