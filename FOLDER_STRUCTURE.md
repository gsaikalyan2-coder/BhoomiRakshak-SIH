# Canonical Folder Structure — LADE

Hybrid of the **full-stack app** and **ML model training** trees: a production API + dashboard
sitting on top of a versioned, explainable risk model.

```
Land Acquisition/
├── backend/
│   ├── app/
│   │   ├── routers/        # thin HTTP handlers only — no logic, no direct DB access
│   │   ├── models/         # SQLAlchemy ORM entities (projects, parcels, awards, disputes, alerts, users)
│   │   ├── schemas/        # Pydantic request/response contracts — every endpoint validated
│   │   ├── services/       # ALL business logic + DB access (risk scoring, alerting, recommendations)
│   │   ├── middleware/     # JWT auth, RBAC, request logging, audit trail
│   │   ├── core/           # config, settings, security primitives, DB session
│   │   └── ml/             # inference adapters — loads the registered model, never trains
│   └── tests/
├── ml/
│   ├── data/               # DVC/pointer-tracked; raw + interim are gitignored
│   ├── src/
│   │   ├── data/           # loading, temporal splits, leakage checks
│   │   ├── features/       # feature definitions shared with backend at inference time
│   │   ├── models/         # XGBoost / LightGBM definitions
│   │   ├── training/       # train loops + experiment configs
│   │   ├── evaluation/     # metrics, per-state/per-stage slices, calibration
│   │   ├── explainability/ # SHAP value computation and reason-code mapping
│   │   └── serving/        # model registry write, artifact packaging
│   ├── experiments/        # tracked runs and the model registry
│   ├── notebooks/          # exploration only — nothing production depends on them
│   ├── monitoring/         # drift + performance decay, retrain triggers
│   ├── config/
│   └── tests/
├── frontend/
│   ├── public/
│   └── src/{components,pages,hooks,services,context,assets,styles}/
├── migrations/             # version-controlled schema changes + PostGIS setup + seed/
├── docker/
├── docs/{research,design,phases,handover}/
├── .github/workflows/      # ci.yml + deploy.yml
├── scripts/
├── docker-compose.yml
├── .env.example
├── CLAUDE.md
└── README.md
```

## Boundary logic

- **Routers stay thin.** A router parses, authorises, delegates to a service, returns a schema.
  Any `session.query(...)` inside `routers/` is a defect.
- **Feature code is shared, not duplicated.** `ml/src/features/` is the single definition of a
  feature; `backend/app/ml/` imports it so training and inference cannot drift apart.
- **Training never happens in the API process.** `backend/app/ml/` loads a registered artifact
  by version; retraining is an offline job under `ml/`.
- **Explainability is first-class**, not a helper — the system's value proposition is the reason
  codes, so `explainability/` is its own module with its own tests.
- **Migrations are versioned.** PostGIS extension enablement and every spatial index live in
  `migrations/`, never applied by hand.
- **Notebooks are disposable.** Nothing under `backend/` or `ml/src/` may import from `notebooks/`.
- **Secrets never enter git.** Only `.env.example` is committed, with `ENTER_YOUR_VALUE_HERE`
  placeholders filled per phase.
