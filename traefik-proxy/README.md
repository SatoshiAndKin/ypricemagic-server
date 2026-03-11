# traefik-proxy

Repo-local shared Traefik stack for running `ypricemagic-server` and other Docker apps on the same machine.

## Run

```bash
cp env.example .env
docker compose up -d
```

This starts Traefik on `http://localhost:${PORT:-8000}` and creates the shared Docker network `traefik-proxy`.

Start the ypricemagic app services from the repo root in a separate command:

```bash
cd ..
docker compose up --build
```

## Notes

- This proxy is intentionally separated from the app stack so one Traefik instance can serve multiple apps on the same server.
- `ypricemagic-server` routes are scoped by `VIRTUAL_HOST`.
- Other apps can join the same `traefik-proxy` network and add their own Traefik labels.
