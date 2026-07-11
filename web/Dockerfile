# mcpfor.work web surfaces — landing, docs, dashboard (ADR 0003).
# Multi-stage: install → build (standalone) → minimal runner.

# ---- deps ----
FROM node:24-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
# --ignore-scripts: no dependency lifecycle scripts (supply-chain hardening,
# mirrors the CI web job). The build needs none.
RUN npm ci --ignore-scripts

# ---- build ----
FROM node:24-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# The LLM-free invariant is enforced at image build time too, not just in CI.
RUN node scripts/check-no-llm-deps.mjs
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# ---- runner ----
FROM node:24-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
# Run unprivileged.
RUN addgroup -g 1001 -S nodejs && adduser -u 1001 -S nextjs -G nodejs
# Standalone output ships only the traced runtime deps + a server.js.
COPY --from=build --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=build --chown=nextjs:nodejs /app/.next/static ./.next/static
USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]
