# NGO Funding Tracker — Agent Context

Read this first when resuming work on this project.

## What this is

A freemium NGO funding transparency website: users search NGOs, foundations, and people, then explore an interactive funding network graph. Every funding edge requires a public `citation` (annual report, IRS filing, or grant database URL) — the product presents documented money flows and never asserts intent.

## Current state (as of 2026-07-22)

- Fully implemented, 27 tests passing, deployed and verified.
- **Live URL:** https://ngo-funding-tracker.onrender.com (Render free tier, auto-deploys on push to `main`)
- **GitHub:** https://github.com/mrugesh1989/ngo-funding-tracker (public, standalone repo — separate from the parent `projects` repo)
- **Demo pro key:** `demo-pro-key-123` (seeded on startup; enter in the UI's "Pro API key" field or send as `X-API-Key`)

## Commands

```bash
# Local venv uses Python 3.13 (system python3 is 3.9 — too old)
.venv/bin/python -m pytest -q                                  # run tests
.venv/bin/uvicorn ngo_tracker.main:app --app-dir src --reload  # run locally at :8000
git push                                                        # deploys to Render
```

## Architecture

```
static/ (HTML/CSS/JS + Cytoscape.js CDN, no build step)
  -> src/ngo_tracker/main.py     FastAPI boundary: routes, AppError->HTTP mapping, plan gating
     -> plans.py                 free/pro tiers, SHA-256-hashed API keys, depth/export checks
     -> graph.py                 BFS network expansion (MAX_DEPTH=4, 300-node cap)
     -> repository.py            search, entity detail w/ totals, upserts, funding edges
     -> db.py                    SQLAlchemy models: Entity, Funding, ApiKey (SQLite)
     -> seed.py                  cited demo dataset (12 entities, 11 edges)
     -> ingest.py                ProPublica Nonprofit Explorer adapter (timeouts, 3 retries + jitter)
     -> errors.py                AppError hierarchy; HTTP codes only set at boundary
```

Key conventions: domain errors raised in service layer, mapped once in `main.py`'s exception handler; every external call has timeouts and bounded retries; `citation` is mandatory on funding edges (enforced in `repository.add_funding`).

## Freemium model

- Free: search, entity details, graphs to depth 2.
- Pro ($29/mo metadata only — no payments integration yet): depth 4, CSV export, API access.
- UI falls back to depth 2 with an upgrade banner when a free user requests depth 3+.

## Deployment notes

- `render.yaml` blueprint; health check `/api/plans`; `NGO_TRACKER_DB` env var overrides the SQLite path (for a paid-tier mounted disk).
- Free tier: ephemeral filesystem (DB re-seeded each boot), sleeps after ~15 min idle, brief no-server 404 flapping during deploys is normal.

## Known gaps / next steps (in rough priority order)

1. **Real data ingestion** — IATI (widest country coverage), IRS 990 Schedule I bulk (grant-level edges), UK Charity Commission API, EU Transparency Register, OpenSanctions/LittleSis for person links. Each becomes an adapter in `ingest.py` following the ProPublica pattern; there is no CLI/endpoint to trigger ingestion yet.
2. **Real API keys + payments** — demo key is public in the repo; needs per-customer key issuance (Stripe) and the demo key disabled in production.
3. **Postgres** — swap SQLite before real data volume (repository layer isolates SQL; change `make_engine`).
4. **Graph UX at scale** — "expand node" on click instead of bigger depth; consider raising pro depth once node-cap UX is in.
5. **No ruff config yet** — no `pyproject.toml`; add one if linting is formalized.
