# Build from the repo root: docker build -f services/gateway/Dockerfile .
FROM node:26-slim AS build
RUN corepack enable
WORKDIR /app

# Dependencies first, so source changes don't reinstall them.
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY services/gateway/package.json services/gateway/
RUN pnpm install --frozen-lockfile --filter @ledger/gateway

COPY services/gateway services/gateway
RUN pnpm --filter @ledger/gateway build
RUN pnpm --filter @ledger/gateway --prod deploy --legacy /out

FROM node:26-slim
ENV NODE_ENV=production
WORKDIR /app
COPY --from=build /out .
USER node
EXPOSE 3000
HEALTHCHECK --interval=5s --timeout=3s --start-period=5s --retries=6 \
  CMD ["node", "-e", "fetch('http://127.0.0.1:3000/healthz').then(r=>process.exit(r.ok?0:1),()=>process.exit(1))"]
CMD ["node", "dist/server.js"]
