# Front Le Fil (Next 16).
# ⚠️ API_INTERNAL_URL et NEXT_PUBLIC_FIREBASE_* sont figés AU BUILD (rewrites
# Next et variables publiques inlinées) : ce sont des build-args.

FROM node:22-bookworm-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

ARG API_INTERNAL_URL=http://api:8810
ARG NEXT_PUBLIC_FIREBASE_API_KEY
ARG NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN
ARG NEXT_PUBLIC_FIREBASE_PROJECT_ID
ARG NEXT_PUBLIC_FIREBASE_APP_ID
ENV API_INTERNAL_URL=${API_INTERNAL_URL} \
    NEXT_PUBLIC_FIREBASE_API_KEY=${NEXT_PUBLIC_FIREBASE_API_KEY} \
    NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=${NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN} \
    NEXT_PUBLIC_FIREBASE_PROJECT_ID=${NEXT_PUBLIC_FIREBASE_PROJECT_ID} \
    NEXT_PUBLIC_FIREBASE_APP_ID=${NEXT_PUBLIC_FIREBASE_APP_ID} \
    NEXT_TELEMETRY_DISABLED=1

COPY . .
RUN npm run build


FROM node:22-bookworm-slim
WORKDIR /app
ARG API_INTERNAL_URL=http://api:8810
ARG NEXT_PUBLIC_FIREBASE_PROJECT_ID
ENV NODE_ENV=production \
    PORT=3000 \
    API_INTERNAL_URL=${API_INTERNAL_URL} \
    NEXT_PUBLIC_FIREBASE_PROJECT_ID=${NEXT_PUBLIC_FIREBASE_PROJECT_ID} \
    NEXT_TELEMETRY_DISABLED=1

COPY --from=build --chown=node:node /app/node_modules ./node_modules
COPY --from=build --chown=node:node /app/.next ./.next
COPY --chown=node:node package.json next.config.ts tsconfig.json proxy.ts ./
COPY --chown=node:node lib ./lib

USER node
EXPOSE 3000
CMD ["npm", "run", "start"]
