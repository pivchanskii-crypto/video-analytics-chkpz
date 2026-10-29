# Frontend (React + Vite + TypeScript + TailwindCSS).
# Многоступенчатая сборка:
#   1) node  — сборка статики,
#   2) nginx — раздача SPA и проксирование /api на backend.
FROM node:20-alpine AS build

WORKDIR /app

COPY . .

RUN npm install
RUN npm run build

FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]