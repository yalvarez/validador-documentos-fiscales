#!/bin/sh
# Escribe el archivo de usuarios de la consola desde CONSOLA_HTPASSWD_B64 (lineas "usuario:hash"
# en base64, para que el '$' de los hashes no lo interprete docker compose). Vacio = nadie entra.
set -eu
destino=/etc/nginx/consola.htpasswd
if [ -n "${CONSOLA_HTPASSWD_B64:-}" ]; then
  printf '%s' "$CONSOLA_HTPASSWD_B64" | base64 -d > "$destino"
else
  echo "AVISO: CONSOLA_HTPASSWD_B64 vacio; la consola rechazara todo acceso" >&2
  : > "$destino"
fi
chown root:nginx "$destino"
chmod 640 "$destino"
