# derleme asamasi - Vite build-time ortam degiskenlerini derlenmis statik dosyalara gomuyor,
# bu yuzden calisma zamaninda degil ARG/ENV ile build sirasinda gecirilmeleri gerekiyor
FROM node:20-alpine AS build
WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

ARG VITE_API_URL
ARG VITE_ANALYSIS_SERVICE_URL
ENV VITE_API_URL=${VITE_API_URL}
ENV VITE_ANALYSIS_SERVICE_URL=${VITE_ANALYSIS_SERVICE_URL}

RUN npm run build

# calistirma asamasi - statik dosyalari hafif bir nginx ile sunuyor, node runtime'i gerekmiyor
FROM nginx:alpine AS runtime
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
