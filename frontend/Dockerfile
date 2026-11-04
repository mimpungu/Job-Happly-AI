FROM node:26-alpine AS deps
RUN corepack enable
WORKDIR /srv
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

FROM node:26-alpine AS build
RUN corepack enable
WORKDIR /srv
ARG NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /srv/node_modules ./node_modules
COPY . .
RUN pnpm build

FROM node:26-alpine AS run
WORKDIR /srv
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=3000
COPY --from=build /srv/.next/standalone ./
COPY --from=build /srv/.next/static ./.next/static
COPY --from=build /srv/public ./public
USER node
CMD ["node", "server.js"]
