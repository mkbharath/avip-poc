# AVIP PoC — Deployment Guide

## Architecture

```
Shared Nginx (managed by DevOps)
   │
   ├── avip.ideyalabs.com → http://127.0.0.1:5174 (AVIP)
   └── oia.ideyalabs.com  → http://127.0.0.1:5173 (OIA)
```

AVIP runs as a self-contained Docker Compose stack. The frontend container (Nginx) handles internal routing to the API. DevOps only needs to point the subdomain to port 5174.

## Port Allocation

| Service | Port | Notes |
|---------|------|-------|
| AVIP Frontend (Nginx) | **5174** | Serves SPA + proxies /api/ and /static/ to API |
| AVIP API (FastAPI) | **8001** | Internal only (frontend proxies to it) |

## Info for DevOps

Add to the shared Nginx:

```
Subdomain: avip.ideyalabs.com
Upstream:  http://127.0.0.1:5174
```

The frontend container handles all internal routing — no path-level proxy rules needed at the edge. Just forward everything to 5174.

## Deployment

```bash
cd /opt/avip-poc   # or wherever
git clone <repo-url> .
./deploy/deploy.sh
```

## Management

```bash
# Logs
docker compose -f docker-compose.prod.yml logs -f

# Restart
docker compose -f docker-compose.prod.yml restart

# Rebuild after code changes
docker compose -f docker-compose.prod.yml build && docker compose -f docker-compose.prod.yml up -d

# Reset demo data
curl -X POST http://localhost:8001/api/v1/demo/reset

# Stop
docker compose -f docker-compose.prod.yml down
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Port conflict | `ss -tlnp \| grep -E '5174\|8001'` |
| API unhealthy | `docker compose -f docker-compose.prod.yml logs avip-api` |
| 502 from edge | Ensure containers running: `docker ps \| grep avip` |
| Images not loading | Check demo_data volume: `docker exec avip-api ls /app/demo_data/images` |
