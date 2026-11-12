# Consola web (Vite/React) servida en /client por nginx, que exige usuario y contrasena y reenvia
# /client/api a la API agregando la API key.
FROM node:20-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . ./
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html/client
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --chmod=755 consola-htpasswd.sh /docker-entrypoint.d/15-consola-htpasswd.sh
# Nombre de contenedor, no de servicio: en la red compartida de Traefik otro proyecto podria tener
# un servicio "backend" y recibiria la API key.
ENV API_UPSTREAM=http://validador-backend:8000
EXPOSE 80
