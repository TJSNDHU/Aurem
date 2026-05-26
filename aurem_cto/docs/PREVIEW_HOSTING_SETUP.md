# AUREM CTO — Public preview hosting at `preview.aurem.live`

> Iter D-33 · Watchdog-tracked P0 item 2.

The renderer is already shipped and live on the preview URL right now at
`/preview/:project_id`. It reads the public manifest endpoint at
`/api/preview/projects/<id>/manifest` (no auth required).

To take it from the preview domain to the public apex `preview.aurem.live`,
you (the founder) need to do exactly two things on the production box +
your DNS registrar.

---

## Step 1 — DNS A record

At your registrar (Cloudflare / Namecheap / etc.) add **one** A record:

| Type | Name      | Value (replace with your prod box IP)        | TTL |
|------|-----------|-----------------------------------------------|-----|
| A    | `preview` | `<production server public IPv4>`            | 300 |

That points `preview.aurem.live` at the production server. If you front
Cloudflare, set the orange-cloud proxy ON — Cloudflare terminates TLS for
you in addition to Caddy. (Either way works.)

---

## Step 2 — Caddy reverse proxy

Drop this block into `/etc/caddy/Caddyfile` on the production server,
then run `sudo systemctl reload caddy`.

```caddy
preview.aurem.live {
    encode zstd gzip

    # Public manifest API — no auth, served by FastAPI :8001
    @manifest path /api/preview/*
    handle @manifest {
        reverse_proxy localhost:8001
    }

    # Everything else → React SPA :3000, which renders <PublicProjectPreview />
    # at the /preview/:project_id route already registered in App.js.
    reverse_proxy localhost:3000
}
```

Caddy auto-issues the Let's Encrypt TLS cert on the first HTTPS request
(production LE, not staging). Open ports 80 + 443 on the host firewall
if you haven't already.

---

## Step 3 — Verify

From any other machine:

```bash
dig +short preview.aurem.live          # should return your prod IP
curl -I https://preview.aurem.live/preview/<known-project-id>
# expect: HTTP/2 200, server: Caddy
```

Hit `https://preview.aurem.live/preview/<id>` in a browser. You should
see the customer's live build preview with the AUREM header bar showing
`preview.aurem.live · <project-id> · <phase> · <pct>% built`.

---

## Why this folder?

Watchdog rule from the D-31 isolation contract: every piece of AUREM CTO
infrastructure docs + code lives under `/app/aurem_cto/` so the module
can be lifted into its own repo + domain on one day's notice. This
file is non-code documentation but still part of the AUREM CTO product
surface (preview hosting is the customer's first impression).
