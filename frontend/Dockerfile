# syntax=docker/dockerfile:1

# --- Dependencies: cached until package-lock.json actually changes -----------------------
FROM node:24-alpine AS deps

# Next's prebuilt native binaries (SWC / Turbopack) expect glibc symbols that musl omits.
RUN apk add --no-cache libc6-compat

WORKDIR /app

COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci

# --- Builder: produce .next/standalone ---------------------------------------------------
FROM node:24-alpine AS builder

RUN apk add --no-cache libc6-compat

WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# `NEXT_PUBLIC_*` values are inlined into the client bundle at *build* time, so the API URL
# is baked into the image and cannot be changed with `docker run -e`. Point a deployment at
# a different API by rebuilding:
#   docker build --build-arg NEXT_PUBLIC_API_BASE_URL=https://api.example.com .
# Whatever value is used here must also appear in the backend's TEXTROPY_CORS_ORIGINS.
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL

ENV NEXT_TELEMETRY_DISABLED=1

RUN npm run build

# --- Runtime -----------------------------------------------------------------------------
FROM node:24-alpine AS runtime

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

WORKDIR /app

# uid 10001 matches the backend image, so both services map to the same unprivileged id.
RUN addgroup --system --gid 10001 textropy \
    && adduser --system --uid 10001 --ingroup textropy textropy

# server.js and the traced runtime dependencies. The standalone bundle deliberately
# excludes .next/static, which has to be copied alongside it or every asset 404s.
COPY --from=builder --chown=textropy:textropy /app/.next/standalone ./
COPY --from=builder --chown=textropy:textropy /app/.next/static ./.next/static
# NOTE: there is no public/ directory in this app. Add
#   COPY --from=builder --chown=textropy:textropy /app/public ./public
# if one is ever introduced — server.js serves it automatically once present.

USER textropy
EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD node -e "fetch('http://127.0.0.1:3000/').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

# The standalone server, not `next start` — there is no next CLI in this image.
CMD ["node", "server.js"]
