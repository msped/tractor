# Stage 1: Install dependencies
FROM node:24.18.0-alpine3.24 AS deps
WORKDIR /app
COPY package*.json ./
RUN npm ci

# Stage 2: Build the application
FROM node:24.18.0-alpine3.24 AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# The client bundle talks to its own origin via relative URLs, so no public
# host/URL needs to be baked in at build time — the image is origin-agnostic
# and the same build runs in any environment.
RUN npm run build

# Stage 3: Production runner
FROM node:24.18.0-alpine3.24 AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
