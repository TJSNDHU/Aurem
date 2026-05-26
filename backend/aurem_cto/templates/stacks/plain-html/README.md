# Plain HTML

Caddy serves a static `site/` directory. Zero build step, zero runtime.
TLS auto-issued by Let's Encrypt on the first HTTPS request.

  - Drop your `index.html`, CSS, and assets into `site/`.
  - Edit `Caddyfile` to set your domain.
  - That's it. `docker compose up -d` and you're live.

Best for: landing pages, link-in-bio, documentation sites, prototypes.
