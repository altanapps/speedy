# Static site server for getspeedy.app.
#
# Caddy is overkill-free for this: single Go binary, ~5MB image, gzips
# automatically, substitutes $PORT in the Caddyfile so Railway's injected
# port lands on the listening socket.
FROM caddy:2-alpine

COPY Caddyfile /etc/caddy/Caddyfile
COPY . /srv
