# React + FastAPI

The AUREM CTO default stack. Used by 9/10 customers shipping a product
landing + dashboard + a small REST API.

  - `api/`: FastAPI (Python 3.11), routes prefixed `/api/*`.
  - `ui/`: React (CRA + craco), reverse-proxied by Caddy in front.
  - `mongo`: MongoDB 7 with named volume.

Ports: ui=3000, api=8001, mongo=27017. Deploy command stays identical
across all stacks: `git pull && docker compose up -d --build`.
