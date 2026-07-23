# NGO Funding Tracker

Search NGOs, foundations, and people, then explore their funding network as an interactive graph. Every funding edge stores a mandatory public citation (annual report, IRS Form 990, or grant database URL) — the product shows documented money flows and lets users draw their own conclusions.

## Quick start

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn ngo_tracker.main:app --app-dir src --reload
```

Open http://127.0.0.1:8000 — the database is created and seeded with a cited demo dataset on first start.

## Tests

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
```

## API

| Endpoint | Plan | Description |
|---|---|---|
| `GET /api/search?q=&type=` | free | Search entities by name; optional type filter |
| `GET /api/entities/{id}` | free | Entity detail with funded/received totals |
| `GET /api/entities/{id}/network?depth=` | free ≤ 2, pro ≤ 4 | Funding network graph around an entity |
| `GET /api/entities/{id}/export.csv?depth=` | pro | CSV export of the network with citations |
| `GET /api/plans` | free | Plan and pricing metadata |

Pass a pro API key in the `X-API-Key` header. A demo key (`demo-pro-key-123`) is seeded for local testing; production keys are issued per customer and stored hashed (SHA-256).

## Deploy to Render

The repo includes a [`render.yaml`](render.yaml) blueprint:

1. Push this folder to a GitHub repository.
2. In the [Render dashboard](https://dashboard.render.com), choose **New > Blueprint** and select the repo. Render reads `render.yaml` and creates the web service automatically.
3. Deploys run on every push to the default branch. The health check hits `/api/plans`.

Notes:

- The free instance has an ephemeral filesystem and sleeps after inactivity; the app re-seeds the demo dataset on every boot, so it always works.
- For persistent data, upgrade the service, attach a disk (e.g. mounted at `/var/data`), and set the `NGO_TRACKER_DB` environment variable to `/var/data/tracker.db` (or move to managed Postgres).
- Before going public, replace the seeded demo key with real per-customer keys.

## Monetization (freemium)

- **Free** — search, entity details, network graphs up to depth 2.
- **Pro ($29/mo)** — depth up to 4, CSV export, programmatic API access.

Later: team plans, saved investigations, alerts on new filings, embeddable graphs for newsrooms.

## Architecture

```
Browser (static HTML/JS + Cytoscape.js)
   → FastAPI boundary (error mapping, plan gating)
      → graph service (BFS traversal, node caps)
         → repository (SQLAlchemy)
            → SQLite (swap for Postgres in production)
```

- `src/ngo_tracker/errors.py` — typed error hierarchy; HTTP mapping happens only in `main.py`.
- `src/ngo_tracker/ingest.py` — ProPublica Nonprofit Explorer adapter (timeouts, bounded retries with backoff and jitter).
- `src/ngo_tracker/seed.py` — demo dataset; every edge cites a public source.

## Data source roadmap

1. **ProPublica Nonprofit Explorer** (wired) — US nonprofit catalog from IRS filings.
2. **IRS Form 990 bulk data (Schedule I)** — grant-level funder → recipient edges at scale.
3. **EU Transparency Register** — EU lobbying and NGO funding disclosures.
4. **UK Charity Commission API** — UK charity accounts and income sources.
5. **OpenSanctions / LittleSis** — person ↔ organization relationship enrichment.

## Editorial policy

Only documented, citable funding relationships are stored (`citation` is required at the schema level). The site never asserts intent or wrongdoing; it presents public records with sources.
