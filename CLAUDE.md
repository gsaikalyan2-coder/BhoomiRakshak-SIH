# CLAUDE.md — Execution Contract

Read this file **before every phase**. It governs. If a plan document contradicts it, this file wins.

## Project

**BhoomiRakshak — Land Acquisition Delay Early-Warning System**
SIH 2026 · PS **SIH26017** · Ministry of Rural Development · Category: Software · Theme: Agriculture, Foodtech

Predict which ongoing land acquisition projects will slip, explain why per project, and prescribe
corrective action — for **government officers only**. No public surface, ever.

## Tech stack (fixed)

| Layer | Choice |
|---|---|
| Database | PostgreSQL 16 + PostGIS 3 |
| Backend | FastAPI (Python 3.11), SQLAlchemy 2.x, Pydantic v2, Alembic |
| Model | XGBoost / LightGBM — risk classification + delay-stage prediction |
| Explainability | SHAP (TreeExplainer) |
| Recommendations | Rule-based mapping + Flan-T5 for natural-language phrasing |
| Frontend | React 18 + Vite, Recharts, Leaflet.js |
| Alerts | Webhook + SMTP on risk-threshold breach |
| Auth | JWT, role-based (admin / officer) |

Do not introduce a new framework, database, or model family without an explicit decision record
in `docs/design/`.

## Repository structure

See `FOLDER_STRUCTURE.md`. Directory boundaries there are binding.

## Conventions

- **Routers thin, services fat.** No DB access outside `backend/app/services/`.
- **Every endpoint has a Pydantic request and response schema.** No bare dicts.
- **Every foreign key has an index.** Every geometry column has a GiST index.
- **Feature definitions live once**, in `ml/src/features/`, imported by both training and serving.
- **No TODO placeholders in committed code.** If it isn't built, it isn't merged.
- **No fabricated data presented as real.** Synthetic/demo data is labelled as such in the UI.
- **Audit everything.** Every officer action that changes project state writes an audit row.
- Python: `ruff` + `black`, type hints required on service functions. JS: ESLint + Prettier.
- Commits: `type(scope): summary`.

## API surface

`/api/v1` — routes are defined per phase. Keep this table current as routes land.

| Method | Path | Purpose | Role |
|---|---|---|---|
| — | — | *(none yet — scaffold only)* | — |

## Data schema

Core entities (to be defined in `migrations/`): `projects` (PK = **ULPIN**, 14-digit
DILRMP-style `29-007-760-288390`; state and district codes verified correct against Census 2011
in the working dataset), `risk_history` (4-6 timestamped snapshots per project, required by the trend
chart), `status_log` (desk-level timestamps, required by the SLA/stuck-file clock), `officers`
(seeded, format `TN-LAO-2024-0456` / `TN-DC-2019-0012`), `risk_scores`, `risk_reasons`,
`recommendations`, `alerts`, `annotations`, `audit_log`.

Scope of record and build order: `docs/design/scope.md`. Gap coverage: `docs/research/gap-coverage-matrix.md`.

## Environment variables — fill schedule

Secrets are filled **in the phase that first needs them**, only in local `.env`, never committed.

| Variable | Filled in | Source |
|---|---|---|
| `POSTGRES_*`, `DATABASE_URL` | Phase 1 (data layer) | local Postgres/PostGIS container |
| `JWT_SECRET_KEY` | Phase 2 (auth) | generate: `openssl rand -hex 32` |
| `ACTIVE_MODEL_VERSION`, `MODEL_REGISTRY_PATH` | Phase 4 (model serving) | output of first training run |
| `FLAN_T5_MODEL_NAME`, `HF_HOME` | Phase 5 (recommendations) | Hugging Face model id |
| `ALERT_WEBHOOK_URL`, `SMTP_*`, `ALERT_RISK_THRESHOLD` | Phase 6 (alerts) | [CLIENT-TBD] |
| `VITE_*` | Phase 3 (frontend) | local API base URL |

## Phase execution rules

1. Execute **one phase at a time**. Do not start the next phase until the user confirms.
2. A phase is done only when its **binary exit criterion** is verified — not when work was done on it.
3. At the end of every phase, produce a handover file `docs/handover/handover_phase_X.txt`
   containing: Part A project summary + current status + phase just completed; Part B what this
   session accomplished (decisions, files created/modified, blockers); Part C everything a cold
   session needs to resume without chat history.
4. Wait for the user to confirm receipt of the handover before proceeding.
5. Update `## Current Phase

**Phase 2 — ML core: COMPLETE (verified 2026-08-23, 10/10 exit checks). Phase 3 — Backend API + auth: NOT STARTED.**

Delivered in Phase 2: `ml/src/features/` as the single feature-definition module (drop-list,
explicit ordinal encodings, one-hot levels, `FeatureSpec` frozen column contract) imported by
both training and, from Phase 3, serving; Model A (XGBoost binary `is_delayed`, 600 closed
projects, isotonic-calibrated) and Model B (XGBoost 5-class `delay_stage`, conditional on
delay); the three derived scores (compensation-gap index, litigation-propensity score,
succession risk) computed per project and persisted to the registry;
`ml/src/explainability/` (`shap.TreeExplainer` plus a reason-code map turning feature names
into officer language); `ml/src/evaluation/` writing a CV report card; a versioned model
registry with `ACTIVE_MODEL_VERSION` and `MODEL_REGISTRY_PATH` set in `.env`;
21 unit tests; and `scripts/verify_phase2.py`.

Verified (out-of-fold, 5-fold stratified CV): binary **AUC 0.9212**, accuracy 0.8567,
Brier 0.113 · 5-class stage accuracy **0.7127 vs 0.3470 majority baseline = 2.05x** ·
21/21 tests pass including the drop-list assertion · `title_clarity_status` 0.0742 and
`legal_dispute_stage` 0.0523 gain share, with the literal `"None"` preserved on 186 rows ·
three hand-picked projects each return three officer-language SHAP factors ·
the succession band and reason match the seeded `succession_risk` table on 362/362 parcels.

Active model version: `v2026-08-23T12-16-56` under `ml/experiments/registry/`.

Two Phase 2 decisions that bind later phases: derived scores are **application** features and
are never model inputs (feeding them back cannibalises the SHAP importance of the raw drivers
an officer needs named); and calibration is a **separate isotonic artifact** beside the raw
booster, because `shap.TreeExplainer` cannot walk a calibrated wrapper — serving calls
`RiskExplainer.calibrated_probability()` rather than re-implementing it.

Carried forward from Phase 1, unchanged: `status_log` holds the desk chain within a project's
**current stage only**, so the SLA clock (N7) must be desk-based, not stage-based; district
polygons are **derived convex hulls** of village centroids and must be labelled approximate in
the UI; `docker compose up -d db` was never verified in a build session.

Environment: `.env` holds `POSTGRES_*`, `DATABASE_URL`, `MODEL_REGISTRY_PATH` and
`ACTIVE_MODEL_VERSION`. Everything else is still `ENTER_YOUR_VALUE_HERE`; Phase 3 fills
`JWT_SECRET_KEY` and `VITE_API_BASE_URL`.

Next: Phase 3 (Backend API + auth) — awaiting the user's confirmation of receipt of
`docs/handover/handover_phase_3.txt`.
