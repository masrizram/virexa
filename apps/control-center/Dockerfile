# Virexa Control Center — Next.js
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json ./
# Windows-generated lockfile may contain platform-specific entries; resolve fresh on Linux.
RUN npm install --no-audit --no-fund

FROM node:22-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
# Public, non-secret env baked at build:
ARG NEXT_PUBLIC_API_BASE_URL=""
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000
RUN addgroup -S virexa && adduser -S virexa -G virexa
COPY --from=build --chown=virexa:virexa /app/.next ./.next
COPY --from=build --chown=virexa:virexa /app/node_modules ./node_modules
COPY --from=build --chown=virexa:virexa /app/package.json ./package.json
USER virexa
EXPOSE 3000
CMD ["npx", "next", "start", "-p", "3000"]
