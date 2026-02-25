# Incident Response Runbook

## Price Endpoint Returning 500

1. Check container logs: `docker compose logs ypm-<chain> --tail=100`
2. Verify RPC endpoint is reachable: `curl -s $RPC_URL_ETHEREUM` (or relevant chain)
3. Check brownie network status in logs for "chain_connected" event
4. If RPC is down, update `RPC_URL_<CHAIN>` in `.env` and restart: `docker compose restart ypm-<chain>`

## Container Unhealthy

1. Check health: `docker compose ps`
2. View logs: `docker compose logs ypm-<chain> --tail=200`
3. Common causes:
   - RPC URL unreachable at startup (brownie connect fails)
   - Invalid ETHERSCAN_TOKEN (explorer requests fail)
   - Port conflict on 8001
4. Restart a single chain: `docker compose restart ypm-<chain>`
5. Full restart: `docker compose down && docker compose up -d`

## Cache Issues

- Cache location: Docker volume `cache-<chain>` mounted at `/data/cache`
- To clear cache for a chain: `docker compose down ypm-<chain> && docker volume rm ypricemagic-server_cache-<chain> && docker compose up -d ypm-<chain>`
- Cache read/write failures are non-fatal — prices are still returned, just not cached

## High Latency

1. Price lookups without cache hit require on-chain RPC calls (can be slow for complex tokens)
2. Check `/metrics` endpoint for `price_request_duration_seconds` histogram
3. dank_mids batches RPC calls — verify it patched successfully ("dank_mids_patched" in startup logs)

## Rollback

To roll back to a previous Docker image:

```bash
# Pull a specific image tag
docker pull ghcr.io/satoshiandkin/ypricemagic-server:sha-<commit>

# Update docker-compose.yml to pin to that image, then:
docker compose up -d
```
