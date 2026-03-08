# User Testing

## Testing Surface

**Backend API:**
- Test via pytest TestClient (no Docker needed)
- If Docker running: curl to http://localhost:8000/{chain}/endpoint

**Frontend Svelte App:**
- Dev server: `cd frontend && npm run dev` → http://localhost:5173
- agent-browser can navigate and interact with the Svelte app
- All form interactions testable via browser automation

**Full Stack (Docker):**
- `docker compose up -d --build`
- Wait for health: `curl -sf http://localhost:8000/ethereum/health`
- Frontend at http://localhost:8000/
- API at http://localhost:8000/{chain}/endpoint
- Docs at http://localhost:8000/{chain}/docs

## Testing Tools

- **agent-browser**: For frontend UI testing (forms, modals, autocomplete, theme)
- **curl**: For API endpoint testing
- **pytest**: For backend unit/integration tests
- **vitest**: For frontend unit tests

## Known Quirks

- Backend containers take 30-60s to start (brownie network registration)
- Bucket classification is slow (10-30s per call)
- The tokenlist proxy requires a valid HTTPS URL to a tokenlist endpoint
- Amount-based price queries are not cached and may be slow
