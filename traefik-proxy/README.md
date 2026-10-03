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

Keep `driver: bridge` explicit. Existing deployments record that setting in the
network configuration hash. Removing it makes Compose try to recreate the shared
network, which fails while other app containers remain attached.

Unhealthy or starting app containers keep their configured routes, so unavailable
services return a server error instead of an unrelated HTTP 404. They receive no
requests until their Docker health check succeeds. To receive HTTP 503 for an
empty service on Traefik 3.7, let Docker select the port from the image's single
`EXPOSE` declaration. Keep an explicit service name with a load-balancer setting
such as `traefik.http.services.<name>.loadbalancer.passhostheader=true`; an explicit
`server.port` label leaves a partial server entry and produces HTTP 500 while
unhealthy. Apps that expose multiple ports still require an explicit port.

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
