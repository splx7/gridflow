# GridFlow

Hybrid microgrid sizing and simulation platform for distributed energy systems. Design PV + battery + diesel generator systems, run hourly dispatch simulations with optimal LP or heuristic strategies, and evaluate economics (NPC, LCOE, IRR) — all from a modern web interface.

## Features

- **Component modelling** — Solar PV (single-diode), wind turbines (power curve), batteries (cycle degradation), diesel generators, grid connections
- **Dispatch simulation** — Load-following, cycle-charging, combined heuristic, and HiGHS LP optimal (8760-hour, ~70k variables)
- **Economics** — Net Present Cost, LCOE, IRR, payback period, battery replacement scheduling
- **Sensitivity analysis** — One-at-a-time (OAT) sweeps with tornado and spider chart visualisation
- **Network analysis** — Newton-Raphson AC power flow, IEC 60909 short circuit, N-1 contingency, cable/transformer libraries
- **Grid code compliance** — IEC, Fiji, IEEE 1547 profiles with configurable voltage/frequency limits
- **FREF mode** — Fiji Rural Electrification Fund templates, rural village load profiles, cyclone derating, per-household cost metrics
- **PDF reports** — 13-section professional feasibility study with charts, system diagrams, and FREF-specific analysis
- **Project management** — Templates, duplicate, JSON export/import, comparison overlay
- **Infrastructure** — Docker Compose deployment, rate limiting, password strength validation, health checks

## Architecture

```
frontend/          Next.js 14 (App Router) + TypeScript + Tailwind + shadcn/ui
backend/
  app/             FastAPI + SQLAlchemy (async) + Celery + Redis
  engine/          Pure Python numerical engine (no web dependencies)
  alembic/         PostgreSQL migrations
```

## Quick Start (Docker)

```bash
docker compose up --build
```

Services: PostgreSQL :5432, Redis :6379, Backend API :8000, Celery worker, Frontend :3000

## Local Development

### Prerequisites

- Python 3.12+
- Node.js 18+
- PostgreSQL 16
- Redis

### Backend

```bash
cd backend/
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Copy and edit environment variables
cp .env.example .env

# Run migrations
PYTHONPATH=. alembic upgrade head

# Start API server
PYTHONPATH=. uvicorn app.main:app --host 0.0.0.0 --port 8000

# Start Celery worker (separate terminal)
PYTHONPATH=. celery -A app.worker.celery_app worker --loglevel=info --concurrency=1
```

### Frontend

```bash
cd frontend/
npm install
NEXT_PUBLIC_API_URL="http://localhost:8000" npm run build
npm run start
```

### Mac Mini M4 (16GB) Notes

Next.js dev mode causes kernel panics on memory-constrained machines. Always use production builds:

```bash
# Frontend — NEVER use `npm run dev`
NEXT_PUBLIC_API_URL="http://100.108.47.61:8000" npm run build
NODE_OPTIONS="--max-old-space-size=256" npm run start -- --hostname 0.0.0.0

# Backend — skip --reload flag
PYTHONPATH=. uvicorn app.main:app --host 0.0.0.0 --port 8000

# Celery — limit concurrency
PYTHONPATH=. celery -A app.worker.celery_app worker --loglevel=info --concurrency=1
```

## Running Tests

```bash
cd backend/

# All tests (engine + API)
PYTHONPATH=. python -m pytest tests/ -v

# Engine unit tests only
PYTHONPATH=. python -m pytest tests/engine/ -v

# API integration tests only
PYTHONPATH=. python -m pytest tests/api/ -v
```

## API Documentation

With the backend running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Project Structure

```
backend/
  app/
    api/v1/          REST endpoints (auth, projects, components, simulations, ...)
    core/            Security, dependencies, rate limiting
    models/          SQLAlchemy models (User, Project, Component, Simulation, ...)
    schemas/         Pydantic request/response schemas
    worker/          Celery tasks (simulation, sensitivity analysis)
  engine/
    solar/           Single-diode PV model, irradiance, solar geometry
    load/            Load profile generation (residential, commercial, industrial, rural village)
    dispatch/        HiGHS LP optimal dispatch
    simulation/      Dispatch runner (heuristic strategies)
    economics/       NPC/LCOE/IRR, Fiji FREF presets
    network/         Power flow, grid codes, topology, contingency, cable library
    advisor/         BESS auto-sizing, network advisor
    reporting/       PDF report generation
    data/            Component templates, project templates
  tests/
    engine/          Unit tests for numerical engine
    api/             Integration tests for REST API
  alembic/           Database migrations

frontend/
  src/
    app/             Next.js pages and layouts
    components/      React components (dashboard, configure, results, UI)
    lib/             API client, utilities
    hooks/           Custom React hooks
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14, TypeScript, Tailwind CSS, shadcn/ui, Recharts, React Flow |
| Backend API | FastAPI, Pydantic v2, SQLAlchemy 2.0 (async) |
| Task queue | Celery, Redis |
| Database | PostgreSQL 16 |
| Solver | HiGHS (via highspy) |
| PDF | ReportLab, Matplotlib |
| Deployment | Docker Compose |
