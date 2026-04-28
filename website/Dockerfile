# Static site server for getspeedy.app.
#
# Caddy: single Go binary, ~5MB image, gzips automatically, substitutes
# $PORT in the Caddyfile so Railway's injected port lands on the listening
# socket.
#
# We COPY the whole folder for /srv (so future assets — CSS, images — get
# picked up automatically), then rm the build-only files so they don't get
# served at /Dockerfile, /Caddyfile, /.dockerignore.
FROM caddy:2-alpine

COPY Caddyfile /etc/caddy/Caddyfile
COPY . /srv
RUN rm -f /srv/Dockerfile /srv/Caddyfile /srv/.dockerignore
