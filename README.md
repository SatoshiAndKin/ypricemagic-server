# traefik-proxy

Repo-local shared Traefik stack for running `ypricemagic-server` and other Docker apps on the same machine.

## Run

```bash
cp env.example .env
docker compose up -d
```

This starts Traefik on loopback and creates the shared Docker network
`traefik-proxy`. The `web` entrypoint uses port `${PORT:-8000}`; `web2` uses
`${SECONDARY_PORT:-8001}`. The dashboard uses `${DASHBOARD_PORT:-8080}`.

For Tailscale HTTPS, assign apps that share the machine's Tailscale hostname to
different entrypoints. On ski-nuc-3, use `web` for Compare DEX Routers and `web2`
for ypricemagic-server, with `VIRTUAL_HOST=ski-nuc-3.shorthair-fir.ts.net` in each
app's environment. Set `TRUSTED_PROXY_IPS` to the host's Docker bridge gateway
address with a `/32` prefix so Traefik preserves Tailscale's HTTPS headers.

```bash
sudo tailscale serve --bg --https=443 http://127.0.0.1:8080
sudo tailscale serve --bg --https=8443 http://127.0.0.1:8000
sudo tailscale serve --bg --https=9443 http://127.0.0.1:8001
```

The dashboard is at `https://ski-nuc-3.shorthair-fir.ts.net/dashboard/`.
Compare DEX Routers uses `https://ski-nuc-3.shorthair-fir.ts.net:8443/` and
ypricemagic-server uses `https://ski-nuc-3.shorthair-fir.ts.net:9443/`.
These routes use private Tailscale Serve; do not enable Funnel for them.

Start the ypricemagic app services from the repo root in a separate command:

```bash
cd ..
docker compose up --build
```

## Notes

- This proxy is intentionally separated from the app stack so one Traefik instance can serve multiple apps on the same server.
- `ypricemagic-server` routes are scoped by `VIRTUAL_HOST`.
- Other apps can join the same `traefik-proxy` network and add their own Traefik labels.
