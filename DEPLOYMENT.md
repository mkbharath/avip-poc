# AVIP On-Prem Deployment (Docker Compose)

Single-node pilot deployment of the AVIP portal (FastAPI backend + React/nginx
frontend) on one Linux host, using `docker-compose.prod.yml`.

> **Scope / caveats (pilot, not hardened production):** the datastore is
> **SQLite** (single-node; fine for a pilot, not for concurrent-write scale),
> there is **no authentication** (deploy behind the firewall / a reverse proxy
> you control), and the TPI/vision LLM defaults to a **deterministic mock** (no
> outbound network). Moving to Postgres, adding SSO, and enabling a real LLM are
> tracked in the client questionnaire and are deliberately out of scope here.

## Architecture

- `avip-api` — FastAPI on `:8000` (internal). SQLite DB + uploaded TPI files
  persist in the **`avip-data`** named volume (`/app/data`).
- `avip-frontend` — nginx serving the React build on `:80`, published to the
  host (default host port **8080**). nginx proxies `/api` and `/static` to
  `avip-api` (see `frontend/nginx.conf`).

## First-time setup (already done on your server)

```bash
git clone https://github.com/mkbharath/avip-poc.git
cd avip-poc
git checkout feature/avip-source-comparison
cp .env.prod.example .env.prod        # then edit values (kept local, gitignored)
docker compose -f docker-compose.prod.yml up -d --build
```

---

## Redeploying new changes (the common case)

The **`avip-data` volume is preserved** across image rebuilds and container
recreation, so your ingested/reviewed data survives. New DB tables (e.g. the
`tpi_*` tables) are created additively on startup via `CREATE TABLE IF NOT
EXISTS` — **existing tables and rows are untouched**.

### 1. (Recommended) Back up the SQLite DB first

A redeploy shouldn't touch the data, but back it up anyway — it's cheap:

```bash
# Copy the live DB out of the running container to a timestamped file on the host
docker cp avip-api:/app/data/avip.db "./avip-backup-$(date +%Y%m%d-%H%M%S).db"
```

### 2. Pull the new code

```bash
cd /path/to/avip-poc
git fetch origin
git checkout feature/avip-source-comparison
git pull --ff-only origin feature/avip-source-comparison
```

### 3. Rebuild images and recreate containers

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

- `--build` rebuilds both images with the new code (backend now bakes in the
  TPI `sample_data/` fixtures; frontend rebuilds the React bundle).
- `up -d` recreates only the changed containers. The `avip-data` volume is
  **reused**, not recreated — data persists.
- The backend healthcheck gates the frontend; `up` waits until the API is
  healthy.

### 4. Verify

```bash
# Containers up + healthy
docker compose -f docker-compose.prod.yml ps

# API health
curl -f http://localhost:8000/api/v1/health   # from the host; API is internal
# or through the frontend proxy:
curl -f http://localhost:8080/api/v1/health

# New TPI routes are live (should list the /api/v1/tpi/* endpoints)
curl -s http://localhost:8080/api/v1/tpi/status | head

# Tail logs if anything looks off
docker compose -f docker-compose.prod.yml logs -f avip-api
```

Then browse to `http://<host>:8080`, sign in, and confirm the **TPI Generation**
group appears in the sidebar (TPI Monitor → Review → Final TPIs).

### 5. Rollback (if the new build misbehaves)

```bash
# Return to the previous commit and rebuild
git log --oneline -5                    # find the previous good commit
git checkout <previous-commit-sha>
docker compose -f docker-compose.prod.yml up -d --build

# If data itself was affected, restore the backup from step 1:
docker compose -f docker-compose.prod.yml stop avip-api
docker cp ./avip-backup-<timestamp>.db avip-api:/app/data/avip.db
docker compose -f docker-compose.prod.yml start avip-api
```

## Enabling the real OpenAI provider (optional)

Only if the server has outbound HTTPS to the OpenAI API:

1. Edit `.env.prod`: set `AVIP_TPI_LLM_PROVIDER=openai` and `OPENAI_API_KEY=sk-...`.
2. `docker compose -f docker-compose.prod.yml up -d` (recreates the API with the
   new env — no rebuild needed for an env-only change).
3. In the UI, the TPI Monitor **Provider** selector can also override per run.
   With no key, selecting `openai` returns a clear error and the mock keeps working.

## Notes

- Secrets live only in `.env.prod` on the server (gitignored). Never commit it.
- `sample_data/` is both baked into the image and mounted read-only, so you can
  refresh fixtures without a rebuild.
- Uploaded TPI files persist under the `avip-data` volume (`/app/data/tpi_uploads`).
