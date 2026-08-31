# Multi-stage Docker build for PaymentFlow Frontend Service

# Stage 1: Build React + Vite app
FROM node:22-alpine AS builder
WORKDIR /app

# Copy dependency specifications
COPY package.json ./
RUN npm install

# Copy source files and configuration
COPY . ./

# Build production distribution
RUN npm run build

# Stage 2: Production Nginx Server
FROM nginx:1.27-alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
