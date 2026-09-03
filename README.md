# LADE — Land Acquisition Delay Early-Warning System

**SIH 2026 · PS SIH26017 · Ministry of Rural Development · Software · Agriculture & Foodtech**

Government-internal decision-support system that predicts which ongoing land acquisition
projects are at risk of delay *before* the delay materialises, explains why, and prescribes
corrective action.

> Access is restricted to government officers (admin / district officer roles). There is no
> public-facing surface.

## Repository map

| Path | Purpose |
|---|---|
| `backend/` | FastAPI service — API, auth, persistence, alerting |
| `ml/` | Risk model: features, training, evaluation, SHAP explainability, serving artifacts |
| `frontend/` | React dashboard — Recharts trends, Leaflet GIS, risk queues |
| `migrations/` | Versioned PostgreSQL + PostGIS schema and seed data |
| `docker/` | Container definitions |
| `docs/` | Research, design, phase records, handover files |
| `scripts/` | One-off operational scripts |

See `FOLDER_STRUCTURE.md` for the full tree and directory boundaries, and `CLAUDE.md` for
conventions and the execution contract.

## Status

Scaffold created. Planning not yet started — no phases defined.
