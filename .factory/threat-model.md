# Threat Model for ypricemagic-server

**Last Updated:** 2026-03-09
**Version:** 1.0.0
**Methodology:** STRIDE + Natural Language Analysis

---

## 1. System Overview

### Architecture Description

This is a multi-chain ERC-20 token price API that wraps [ypricemagic](https://github.com/BobTheBuidler/ypricemagic) behind a FastAPI HTTP server. Users query token prices by address and block number across Ethereum, Arbitrum, Optimism, and Base. The system runs one container per chain, all fronted by a Traefik reverse proxy.

The system has **5** main components:

1. **Traefik Reverse Proxy** - Routes requests to the correct chain backend based on URL prefix (`/ethereum`, `/arbitrum`, etc.). Strips the chain prefix, terminates TLS (in production via external load balancer), and serves as the single ingress point on port 80/8000.
2. **FastAPI Backend (per-chain)** - Python server running uvicorn that exposes `/price`, `/prices`, `/quote`, `/check_bucket`, `/health`, `/tokenlist/proxy`, and `/metrics` endpoints. Each container connects to one chain's RPC node via brownie + dank_mids.
3. **Svelte Frontend** - Single-page application served via its own container. Communicates with backends through Traefik using relative URLs (e.g., `/${chain}/price`).
4. **diskcache Layer** - On-disk cache (SQLite-backed) storing token prices keyed by `token:block`. Mounted as Docker volumes at `/data/cache`.
5. **External Dependencies** - RPC nodes (user-provided URLs), Etherscan/block explorer APIs (for contract verification), and the ypricemagic/brownie/dank_mids Python stack for on-chain price resolution.

### Key Components

| Component | Purpose | Security Criticality | Attack Surface |
|-----------|---------|---------------------|----------------|
| Traefik Proxy | Ingress routing, prefix stripping | HIGH | Port 80 (public), Docker socket (host) |
| FastAPI Backend | Price computation, caching, API | HIGH | HTTP endpoints (7 routes per chain) |
| Tokenlist Proxy | CORS bypass for remote tokenlists | HIGH | Outbound HTTP (SSRF risk) |
| diskcache | Price caching | LOW | Local filesystem only |
| Svelte Frontend | Browser UI | MEDIUM | Static assets, API calls |
| Prometheus /metrics | Observability | MEDIUM | Exposes internal counters |
| Docker Socket | Traefik provider | CRITICAL | Read-only mount, but still high-value |

### Data Flow

When a user requests a token price, the frontend sends a GET request to `/{chain}/price?token=0x...&block=12345`. Traefik matches the chain prefix, strips it, and forwards the request to the appropriate backend container on port 8001. The backend validates the token address (regex: `^0x[a-fA-F0-9]{40}$`), checks the diskcache for a hit, and if missing, calls ypricemagic which in turn queries the chain's RPC node. The price is cached and returned as JSON.

For the tokenlist proxy, the frontend sends a URL to `/{chain}/tokenlist/proxy?url=https://...`. The backend validates HTTPS-only, resolves DNS, checks for private/internal IPs (SSRF protection), then fetches the remote tokenlist and returns it.

---

## 2. Trust Boundaries & Security Zones

### Trust Boundary Definition

The system has **3 trust zones**:

1. **Public Zone** - Untrusted external users and systems
   - Assumes: Malicious input, no authentication
   - Entry Points: All HTTP endpoints via Traefik (port 80/8000)
   - Components: Traefik, Frontend static assets

2. **Internal Zone** - Container-to-container communication on `traefik-proxy` Docker network
   - Assumes: Containers are trusted; network is isolated
   - Entry Points: Backend port 8001 (not published to host), Docker internal DNS
   - Components: FastAPI backends, diskcache volumes

3. **External Services Zone** - Outbound connections to third-party systems
   - Assumes: RPC nodes and explorers may be slow, rate-limited, or return unexpected data
   - Entry Points: RPC URLs (env vars), Etherscan APIs, remote tokenlist URLs
   - Components: brownie/web3, httpx client (tokenlist proxy)

### Authentication & Authorization

There is **no authentication or authorization**. All endpoints are publicly accessible. This is by design: the API serves read-only blockchain data that is inherently public. However, this means:

- Any user can query any token price on any supported chain
- Any user can trigger RPC calls to the backend's RPC node
- Any user can use the tokenlist proxy to fetch arbitrary HTTPS URLs (with SSRF protections)
- Prometheus metrics are publicly accessible at `/{chain}/metrics`

**Critical Security Controls:**
- Input validation via regex and type parsing in `src/params.py`
- SSRF protection in tokenlist proxy (`_is_private_ip()`, HTTPS-only)
- CORS middleware (defaults to `*` if `CORS_ORIGINS` not set)
- Log redaction of RPC URLs and API keys via `src/logger.py`
- Rate limiting delegated to upstream infrastructure (not implemented in app)
- Batch endpoint capped at 100 tokens per request

---

## 3. Attack Surface Inventory

### External Interfaces

#### Public HTTP Endpoints

- `GET /{chain}/health` - Health check returning chain name, block height, sync status
  - **Input:** None
  - **Validation:** None needed
  - **Risk:** Information disclosure (chain name, current block, sync state)

- `GET /{chain}/price` - Single token price lookup
  - **Input:** `token` (address), `block` (int), `amount` (float), `skip_cache` (bool), `ignore_pools` (addresses), `silent` (bool), `timestamp` (Unix/ISO)
  - **Validation:** Address regex, block range, amount > 0, bool parsing, timestamp range, block/timestamp mutual exclusivity
  - **Risk:** RPC resource consumption, cache poisoning (if price source returns bad data)

- `GET /{chain}/prices` - Batch token price lookup (up to 100 tokens)
  - **Input:** `tokens` (comma-separated addresses), `block`, `amounts`, `timestamp`, `skip_cache`, `silent`
  - **Validation:** Same as `/price` plus token count limit (100), amounts count must match tokens count
  - **Risk:** Resource amplification (100 parallel RPC calls per request)

- `GET /{chain}/quote` - Token-to-token quote
  - **Input:** `from` (address), `to` (address), `amount` (float), `block`, `timestamp`
  - **Validation:** Both addresses validated, amount > 0, block/timestamp mutual exclusivity
  - **Risk:** Two RPC calls per request, division by zero guarded

- `GET /{chain}/check_bucket` - Token classification
  - **Input:** `token` (address)
  - **Validation:** Address regex
  - **Risk:** Arbitrary ypricemagic execution for unknown tokens

- `GET /{chain}/tokenlist/proxy` - CORS proxy for remote tokenlists
  - **Input:** `url` (string)
  - **Validation:** HTTPS-only, DNS resolution + private IP check, 5 MB limit, 30s timeout
  - **Risk:** SSRF (primary concern), resource consumption from large responses

- `GET /{chain}/metrics` - Prometheus metrics
  - **Input:** None
  - **Validation:** None
  - **Risk:** Information disclosure (request counts, durations, error rates)

- `GET /{chain}/docs` - Swagger UI
  - **Input:** None
  - **Risk:** Exposes full API schema

- `GET /{chain}/redoc` - ReDoc UI
  - **Input:** None
  - **Risk:** Exposes full API schema

### Infrastructure Interfaces

- **Docker Socket** - Mounted read-only into Traefik at `/var/run/docker.sock:ro`
  - **Risk:** Container escape could read container metadata, environment variables, labels
  - **Mitigation:** Read-only mount, but Traefik has full read access to Docker API

- **Traefik Dashboard** - Exposed on `${DASHBOARD_PORT:-8080}`
  - **Risk:** Exposes routing rules, service discovery, middleware config
  - **Mitigation:** `--api.insecure=true` means no auth on dashboard

### Data Input Vectors

1. HTTP query parameters on all API endpoints (primary attack surface)
2. Remote URLs via tokenlist proxy (SSRF vector)
3. Environment variables containing RPC URLs and API keys (secrets)
4. Docker labels for Traefik routing configuration

---

## 4. Critical Assets & Data Classification

### Data Classification

#### Credentials & Secrets

- **RPC_URL_*** (per-chain RPC endpoints) - May contain API keys in URL path or query string. Leaked RPC URLs could allow attackers to consume the user's RPC quota or access private nodes.
- **ETHERSCAN_TOKEN** - API key for block explorer. Leaked key allows quota abuse.
- **GITHUB_TOKEN** (CI only) - Used for Docker image publishing and package access.

**Protection Measures:**
- Log redaction in `src/logger.py` scrubs `rpc_url`, `url`, `host`, `api_key`, `etherscan_token` from log events
- Secrets passed via environment variables (not committed to repo)
- `detect-secrets` pre-commit hook scans for accidental commits
- `.env` is gitignored

#### Business-Critical Data

- **Cached prices** - On-disk SQLite via diskcache. Tampering could cause incorrect price quotes. However, prices are public blockchain data and can be re-fetched.
- **Token classification data** - Bucket classifications from ypricemagic.

#### No PII

This system does not collect, store, or process any personally identifiable information. There are no user accounts, sessions, or tracking.

---

## 5. Threat Analysis (STRIDE Framework)

### S - Spoofing Identity

**What is Spoofing?**
An attacker pretends to be someone or something they're not to gain unauthorized access.

#### Threat: RPC Node Spoofing

**Scenario:** An attacker who controls the network between the backend container and the RPC node could intercept and modify RPC responses, causing the API to return manipulated prices.

**Vulnerable Components:**
- `setup-networks.sh` (brownie network registration)
- `src/server.py` (`_fetch_price`, `_fetch_batch_prices`)

**Attack Vector:**
1. Attacker performs MITM on HTTP RPC connection (if RPC_URL uses `http://` not `https://`)
2. Attacker modifies `eth_call` responses for price oracle contracts
3. Backend caches and serves manipulated price
4. Downstream consumers make financial decisions based on wrong price

**Code Pattern to Look For:**
```python
# VULNERABLE: HTTP RPC URL allows MITM
RPC_URL_ETHEREUM=http://10.11.12.43:8545

# SAFER: HTTPS with TLS verification
RPC_URL_ETHEREUM=https://eth-mainnet.g.alchemy.com/v2/KEY
```

**Existing Mitigations:**
- None enforced at the application level; RPC URL validation is not performed

**Gaps:**
- No validation that RPC URLs use HTTPS
- No TLS certificate pinning for RPC connections

**Severity:** HIGH | **Likelihood:** LOW (requires network position)

#### Threat: Request ID Spoofing

**Scenario:** An attacker sends a crafted `X-Request-ID` header to inject misleading data into logs, potentially confusing incident response or hiding malicious activity.

**Vulnerable Components:**
- `src/server.py` (`request_id_middleware`)

**Code Pattern to Look For:**
```python
# CURRENT: Accepts arbitrary X-Request-ID from client
request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
```

**Existing Mitigations:**
- Request ID is only used for logging/tracing, not for authorization
- structlog sanitizes output

**Gaps:**
- No validation of X-Request-ID format (could inject log-breaking characters)

**Severity:** LOW | **Likelihood:** MEDIUM

---

### T - Tampering with Data

**What is Tampering?**
Unauthorized modification of data in memory, storage, or transit.

#### Threat: Cache Poisoning via Malicious Price Data

**Scenario:** If the upstream price source (ypricemagic/RPC) returns a manipulated price (e.g., due to oracle manipulation or flash loan attack), that price gets cached permanently in diskcache and served to all subsequent requests for that token+block combination.

**Vulnerable Components:**
- `src/cache.py` (`set_cached_price`)
- `src/server.py` (`/price` and `/prices` endpoints)

**Attack Vector:**
1. Attacker manipulates on-chain price oracle at a specific block (e.g., via flash loan)
2. User or attacker queries the API for that token at that block
3. Manipulated price is fetched from chain and cached permanently
4. All future queries for that token+block return the poisoned price

**Code Pattern to Look For:**
```python
# CURRENT: Prices are cached without validation bounds
set_cached_price(params.token, actual_block, price_float, block_timestamp=block_timestamp)

# No sanity check like:
# if price_float > MAX_REASONABLE_PRICE or price_float < MIN_REASONABLE_PRICE:
#     logger.warning("suspicious_price", ...)
```

**Existing Mitigations:**
- NaN, Inf, and negative prices are rejected
- `skip_cache=true` parameter allows bypassing cache
- Prices are keyed by block, so only one block is affected

**Gaps:**
- No price bounds validation or anomaly detection
- No cache invalidation mechanism for poisoned entries
- No TTL on cached entries (they persist forever)

**Severity:** MEDIUM | **Likelihood:** MEDIUM (on-chain oracle manipulation is a known DeFi attack vector)

#### Threat: Tokenlist Proxy Response Tampering

**Scenario:** An attacker hosts a malicious tokenlist that contains misleading token names, symbols, or logos to trick users into interacting with scam tokens.

**Vulnerable Components:**
- `src/server.py` (`/tokenlist/proxy` endpoint)
- Frontend token selection UI

**Attack Vector:**
1. Attacker creates a tokenlist at `https://evil.com/tokenlist.json`
2. User loads this tokenlist via the frontend
3. Tokenlist contains entries with legitimate token names but scam contract addresses
4. User selects a "USDC" entry that actually points to a worthless or malicious contract

**Existing Mitigations:**
- Frontend warns about custom tokenlists (UI responsibility)
- HTTPS-only requirement prevents injection on the wire

**Gaps:**
- No tokenlist schema validation beyond "is valid JSON"
- No allowlist of trusted tokenlist sources
- No checksum/signature verification of tokenlist content

**Severity:** MEDIUM | **Likelihood:** MEDIUM

---

### R - Repudiation

**What is Repudiation?**
Users can deny performing actions because there's insufficient audit logging.

#### Threat: Insufficient Request Attribution

**Scenario:** Without authentication, there is no way to attribute API calls to specific users. If the API is abused (excessive RPC calls, automated scraping), there's no way to identify or block the abuser beyond IP-level controls.

**Vulnerable Components:**
- All API endpoints
- Traefik access logs (if enabled)

**Existing Mitigations:**
- structlog logs include request_id, chain, token, block, duration
- Prometheus metrics track request counts and latencies per chain
- Traefik can log source IPs

**Gaps:**
- No per-user or per-API-key tracking
- No request attribution beyond source IP (which may be behind NAT/proxy)
- No formal audit log with immutable storage

**Severity:** LOW | **Likelihood:** HIGH (abuse is common for public APIs)

---

### I - Information Disclosure

**What is Information Disclosure?**
Exposing information to users who shouldn't have access.

#### Threat: RPC URL / API Key Leakage via Error Messages

**Scenario:** An exception during price fetching could include the RPC URL (containing API keys) in the error message returned to the client.

**Vulnerable Components:**
- `src/server.py` (`_handle_price_error` returns `str(inner)` which may contain RPC URL)
- `src/server.py` (`/quote`, `/prices` error paths)

**Attack Vector:**
1. Attacker sends a request that triggers an RPC connection error
2. The exception message includes the full RPC URL with embedded API key
3. Error message is returned in the JSON response body

**Code Pattern to Look For:**
```python
# VULNERABLE: Exception message may contain RPC URL
return _make_error_response(
    500,
    f"Price lookup failed for {token} at block {block}: {msg}",
)

# The 'msg' variable comes from str(inner) which for connection errors often includes
# the full URL being connected to, e.g.:
# "HTTPConnectionPool(host='eth-mainnet.g.alchemy.com', port=443): Max retries exceeded"
```

**Existing Mitigations:**
- `src/logger.py` redacts sensitive keys in structured log events
- Token addresses are truncated to 10 chars in log messages

**Gaps:**
- Error responses to clients do NOT go through the log redaction pipeline
- Exception messages from web3/brownie/httpx may contain full URLs with API keys
- No scrubbing of error messages before returning to client

**Severity:** HIGH | **Likelihood:** MEDIUM (connection errors happen regularly)

#### Threat: Prometheus Metrics Exposure

**Scenario:** The `/metrics` endpoint is publicly accessible and reveals operational details like request volumes, error rates, and response time distributions per chain.

**Vulnerable Components:**
- `src/server.py` (Prometheus ASGI app mounted at `/metrics`)

**Existing Mitigations:**
- Metrics contain only aggregate counters and histograms, no PII

**Gaps:**
- No authentication on `/metrics` endpoint
- Reveals error rates that could inform targeted attacks

**Severity:** LOW | **Likelihood:** HIGH (trivially accessible)

#### Threat: Traefik Dashboard Exposure

**Scenario:** The Traefik dashboard at port 8080 is configured with `--api.insecure=true`, exposing routing rules, service health, and middleware configuration without authentication.

**Vulnerable Components:**
- `traefik-proxy/docker-compose.yml`

**Code Pattern to Look For:**
```yaml
# VULNERABLE: Dashboard exposed without auth
- "--api.insecure=true"
- "--api.dashboard=true"
ports:
  - "${DASHBOARD_PORT:-8080}:8080"

# SAFE: Dashboard behind auth or disabled in production
# - "--api.dashboard=false"
```

**Existing Mitigations:**
- Dashboard port is configurable and could be firewalled

**Gaps:**
- No authentication middleware on dashboard
- Exposes internal routing topology

**Severity:** MEDIUM | **Likelihood:** HIGH (if port is reachable)

---

### D - Denial of Service

**What is Denial of Service?**
Attacks that prevent legitimate users from accessing the system.

#### Threat: RPC Resource Exhaustion via Batch Endpoint

**Scenario:** An attacker repeatedly calls `/prices` with 100 tokens to trigger 100 parallel RPC calls per request, exhausting the RPC node's rate limits or the backend's resources.

**Vulnerable Components:**
- `src/server.py` (`/prices` endpoint, `_fetch_batch_prices`)
- RPC node (rate limits, connection pools)

**Attack Vector:**
1. Attacker sends rapid requests to `/prices?tokens=0x...,0x...,0x...` (100 unique tokens)
2. Each request triggers up to 100 parallel `get_prices` calls via dank_mids
3. dank_mids batches these into multicall, but each unique token still requires price resolution
4. RPC node rate limits are hit, causing failures for legitimate users

**Code Pattern to Look For:**
```python
# CURRENT: Batch limit is 100 tokens, no rate limiting
MAX_BATCH_TOKENS = 100

# No per-IP or global rate limiting:
# Attacker can send unlimited requests
```

**Existing Mitigations:**
- Batch limit of 100 tokens per request
- `tenacity` retry with exponential backoff (2 attempts max) prevents retry storms
- Cache reduces RPC calls for previously-queried token+block pairs

**Gaps:**
- No application-level rate limiting
- No concurrent request limit per IP
- No global RPC call budget
- 100 tokens * N concurrent requests = unbounded RPC load

**Severity:** HIGH | **Likelihood:** HIGH (trivial to execute, public API)

#### Threat: Tokenlist Proxy as Amplification Vector

**Scenario:** Attacker uses the tokenlist proxy to fetch large (up to 5 MB) responses from slow servers, tying up backend resources.

**Vulnerable Components:**
- `src/server.py` (`/tokenlist/proxy`)

**Attack Vector:**
1. Attacker hosts a server that responds slowly (drip-feeds bytes over 29 seconds)
2. Sends many concurrent requests to `/tokenlist/proxy?url=https://slow.evil.com/huge.json`
3. Each request holds an httpx connection open for up to 30 seconds
4. Backend connection pool is exhausted

**Existing Mitigations:**
- 30-second timeout
- 5 MB response size limit
- HTTPS-only (can't target arbitrary internal services)

**Gaps:**
- No rate limiting on proxy endpoint
- No concurrent connection limit
- Each slow request ties up a worker for up to 30 seconds

**Severity:** MEDIUM | **Likelihood:** MEDIUM

#### Threat: Algorithmic Complexity in Price Resolution

**Scenario:** Certain exotic tokens may trigger extremely expensive price resolution paths in ypricemagic (deep DEX routing, multiple oracle consultations), causing requests to hang for minutes.

**Vulnerable Components:**
- ypricemagic library (external dependency)
- `src/server.py` (`_fetch_price`)

**Existing Mitigations:**
- Retry limited to 2 attempts with exponential backoff
- Cached results prevent repeated expensive lookups

**Gaps:**
- No per-request timeout on `get_price` calls (ypricemagic may hang indefinitely)
- No circuit breaker for consistently slow tokens

**Severity:** MEDIUM | **Likelihood:** MEDIUM

---

### E - Elevation of Privilege

**What is Elevation of Privilege?**
Gaining higher privileges than intended.

#### Threat: Docker Socket Access via Container Escape

**Scenario:** If an attacker achieves code execution in the Traefik container, the read-only Docker socket mount provides access to the Docker API, allowing enumeration of all containers and their environment variables (which contain RPC URLs and API keys).

**Vulnerable Components:**
- `traefik-proxy/docker-compose.yml` (Docker socket mount)
- All containers with secrets in environment variables

**Attack Vector:**
1. Attacker exploits a vulnerability in Traefik (e.g., CVE in the image)
2. Gains shell access in the Traefik container
3. Queries Docker API via the mounted socket: `curl --unix-socket /var/run/docker.sock http://localhost/containers/json`
4. Reads environment variables of all containers, extracting RPC URLs and ETHERSCAN_TOKEN

**Existing Mitigations:**
- Socket is read-only (`:ro`), preventing container creation/modification
- Traefik image is kept updated

**Gaps:**
- Read-only socket still allows reading all container metadata including env vars
- No Docker socket proxy (e.g., Tecnativa/docker-socket-proxy) to limit API access
- Secrets in env vars rather than Docker secrets or mounted files

**Severity:** HIGH | **Likelihood:** LOW (requires Traefik CVE exploitation)

#### Threat: SSRF via Tokenlist Proxy DNS Rebinding

**Scenario:** An attacker bypasses the `_is_private_ip` check using DNS rebinding: the hostname resolves to a public IP during validation, then resolves to a private IP when httpx actually connects.

**Vulnerable Components:**
- `src/server.py` (`_is_private_ip`, `/tokenlist/proxy`)

**Attack Vector:**
1. Attacker registers `evil.com` with a DNS server that alternates between public and private IPs
2. First DNS resolution (in `_is_private_ip`) returns `1.2.3.4` (public) - passes check
3. Second DNS resolution (in httpx.get) returns `169.254.169.254` (cloud metadata) or `127.0.0.1`
4. Backend fetches internal service data and returns it to attacker

**Code Pattern to Look For:**
```python
# VULNERABLE: TOCTOU between DNS check and HTTP request
if _is_private_ip(hostname):  # DNS resolution #1
    return error
response = await client.get(url)  # DNS resolution #2 (may differ!)

# SAFER: Pin resolved IP and connect directly
resolved_ip = socket.getaddrinfo(hostname, ...)
if is_private(resolved_ip):
    return error
# Connect using resolved_ip, not hostname
```

**Existing Mitigations:**
- HTTPS-only (prevents targeting most internal services that don't have valid TLS certs)
- `.local` hostname explicitly blocked
- Private IP ranges checked (RFC 1918, loopback, link-local)

**Gaps:**
- TOCTOU vulnerability between DNS resolution in `_is_private_ip` and httpx connection
- Cloud metadata services (169.254.169.254) may have valid TLS via custom certs
- No IP pinning after initial resolution

**Severity:** MEDIUM | **Likelihood:** LOW (requires DNS rebinding setup, HTTPS requirement limits targets)

---

## 6. Vulnerability Pattern Library

### How to Use This Section

Look for these patterns when reviewing code changes. Each pattern shows a vulnerable example and the safe alternative used (or recommended) in this codebase.

---

### SSRF (Server-Side Request Forgery)

```python
# VULNERABLE: No URL validation
async with httpx.AsyncClient() as client:
    response = await client.get(user_provided_url)

# CURRENT (partially safe): HTTPS-only + private IP check
parsed = urlparse(url)
if parsed.scheme != "https":
    return error
if _is_private_ip(parsed.hostname):
    return error
response = await client.get(url)

# SAFER: Pin resolved IP to prevent DNS rebinding
import socket
addrs = socket.getaddrinfo(hostname, 443)
for addr in addrs:
    ip = ipaddress.ip_address(addr[4][0])
    if ip.is_private or ip.is_loopback or ip.is_link_local:
        return error
# Use transport-level IP pinning (httpx doesn't natively support this)
```

### Information Disclosure via Error Messages

```python
# VULNERABLE: Raw exception in response
return JSONResponse(content={"error": f"Failed: {str(exception)}"})
# May leak: RPC URLs, file paths, internal hostnames

# SAFE: Generic error message
return JSONResponse(content={"error": f"Price lookup failed for {token} at block {block}"})
# Or: scrub known sensitive patterns before returning
```

### Input Validation Bypass

```python
# VULNERABLE: No address validation
token = request.query_params.get("token")
price = await get_price(token, block)

# SAFE (current implementation): Regex validation
ADDRESS_REGEX = re.compile(r"^0x[a-fA-F0-9]{40}$")
if not ADDRESS_REGEX.match(token):
    return error
```

### Resource Exhaustion

```python
# VULNERABLE: Unbounded batch size
tokens = request.query_params.get("tokens").split(",")
prices = await get_prices(tokens, block)  # Could be 10,000 tokens

# SAFE (current implementation): Capped batch size
MAX_BATCH_TOKENS = 100
if len(tokens) > MAX_BATCH_TOKENS:
    return error
```

### Secret Leakage in Logs

```python
# VULNERABLE: Logging raw request/response with URLs
logger.info("request", url=rpc_url, response=resp.text)

# SAFE (current implementation): Structured log redaction
def _redact_secrets(logger, method, event_dict):
    sensitive_keys = {"rpc_url", "url", "host", "api_key", "etherscan_token"}
    for key in list(event_dict.keys()):
        if key.lower() in sensitive_keys:
            event_dict[key] = "[REDACTED]"
    return event_dict
```

### CORS Misconfiguration

```python
# CURRENT: Defaults to allow all origins
_cors_origins = ["*"]  # if CORS_ORIGINS env var is not set

# SAFER: Explicit origin allowlist in production
CORS_ORIGINS=https://ypricemagic.stytt.com
```

---

## 7. Security Testing Strategy

### Automated Testing

| Tool | Purpose | Frequency |
|------|---------|-----------|
| Trivy | Filesystem vulnerability scan | Every PR (`pr-review.yml`) |
| CodeQL (via Trivy SARIF) | Static analysis results in GitHub Security | Every PR |
| detect-secrets | Pre-commit secret scanning | Every commit (pre-commit hook) |
| ruff | Python linting (includes security-adjacent rules) | Every commit + CI |
| mypy | Type checking (catches type confusion bugs) | Every commit + CI |
| deptry | Unused/missing dependency detection | Every commit + CI |

### Manual Security Reviews

Human review is required for:
- Changes to `_is_private_ip()` or tokenlist proxy endpoint (SSRF boundary)
- Changes to `src/logger.py` redaction logic
- New environment variables or secret handling
- Traefik configuration changes
- Docker socket access patterns
- New outbound HTTP endpoints

---

## 8. Assumptions & Accepted Risks

### Security Assumptions

1. **RPC nodes are trusted data sources** - The system assumes RPC responses are accurate. On-chain price manipulation (flash loans, oracle attacks) is outside scope of this API's security boundary; consumers must validate prices independently for high-value transactions.
2. **Docker network isolation is sufficient** - Backend containers communicate only via the `traefik-proxy` network. No container publishes ports to the host except Traefik.
3. **No authentication is needed** - All served data is public blockchain data. The API is read-only and does not modify any on-chain state.
4. **Upstream dependencies are reasonably secure** - ypricemagic, brownie, web3.py, dank_mids are trusted. Trivy scans catch known CVEs.

### Accepted Risks

1. **No application-level rate limiting** - Mitigated by infrastructure (Traefik rate limiting can be configured, cloud load balancer rate limiting). Risk: resource exhaustion. Accepted because adding rate limiting adds complexity and the API is designed for moderate traffic.
2. **CORS defaults to `*`** - This is a public read-only API. Cross-origin access is intentional. Risk: any website can query prices. Accepted because data is public.
3. **Traefik dashboard exposed without auth** - Risk: information disclosure of routing config. Accepted with expectation that the dashboard port is firewalled in production.
4. **DNS rebinding TOCTOU in tokenlist proxy** - The HTTPS-only requirement significantly limits exploitability. Accepted as low-priority.
5. **Cached prices have no TTL or invalidation** - Prices are keyed by block number, which is immutable. A price at block N should never change. Accepted because the cache key design makes this safe for honest data sources.

---

## 9. Threat Model Changelog

### Version 1.0.0 (2026-03-09)

- Initial threat model created
- STRIDE analysis completed for all components
- Vulnerability pattern library established for Python/FastAPI/Docker stack
- Identified 11 threats across 6 STRIDE categories
- Key findings: SSRF DNS rebinding (MEDIUM), RPC URL leakage in error messages (HIGH), no rate limiting (HIGH), Docker socket exposure (HIGH)
