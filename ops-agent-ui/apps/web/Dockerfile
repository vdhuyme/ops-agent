ARG NODE_VERSION=22
ARG PNPM_VERSION=10.6.3

FROM node:${NODE_VERSION} AS deps
# Install pnpm directly via npm. Corepack silently downloads a different
# pnpm version (e.g. 12.8.1 instead of 10.6.3) on recent node base images,
# which breaks Next.js webpack resolution of `@/*` aliases. Using a
# Debian-based `node:22` image (not `-alpine`) avoids the pnpm/musl
# prebuilt-binary issue that Alpine introduces.
RUN npm install -g pnpm@${PNPM_VERSION} \
 && pnpm --version
WORKDIR /repo

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY turbo.json ./
COPY apps ./apps

# `apps/web` declares `next` in `devDependencies`. pnpm 10+ skips devDeps
# whenever NODE_ENV=production — including a base image's inherited value.
# Force NODE_ENV=development here so pnpm installs devDeps for the build.
# Builder stage flips NODE_ENV=production before `next build` itself.
ENV NODE_ENV=development
RUN pnpm install --lockfile --ignore-scripts

FROM node:${NODE_VERSION} AS builder
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_ASSISTANT_ID=agent
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
ENV NEXT_PUBLIC_ASSISTANT_ID=${NEXT_PUBLIC_ASSISTANT_ID}
ENV NEXT_TELEMETRY_DISABLED=1

RUN npm install -g pnpm@${PNPM_VERSION} \
 && pnpm --version
WORKDIR /repo

COPY --from=deps /repo/node_modules ./node_modules
COPY --from=deps /repo/apps ./apps

# `public/` is where Next.js looks for static assets (favicon, images...).
# The source repo doesn't ship one, so create an empty placeholder so the
# runner-stage COPY below has a valid source.
RUN mkdir -p /repo/apps/web/public

ENV NODE_ENV=production
RUN pnpm --filter web build:internal

FROM node:${NODE_VERSION} AS runner
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3002
ENV HOSTNAME=0.0.0.0

WORKDIR /app

# `.next/` is still written by Next.js into the workspace-local directory
# (`apps/web/.next/`), NOT the monorepo root. `outputFileTracingRoot`
# only changes which directory the file tracer scans, not where Next.js
# emits its build output.
#
# Standalone preserves the workspace path structure, so `server.js` lands
# at /app/apps/web/server.js — that's why static assets and `public/` must
# also live under /app/apps/web/.
COPY --from=builder /repo/apps/web/.next/standalone ./
COPY --from=builder /repo/apps/web/.next/static    ./apps/web/.next/static
COPY --from=builder /repo/apps/web/public          ./apps/web/public

EXPOSE 3002

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD wget -qO- http://localhost:3002/ >/dev/null 2>&1 || exit 1

CMD ["node", "apps/web/server.js"]