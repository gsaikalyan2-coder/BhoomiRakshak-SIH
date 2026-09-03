================================================================================
BhoomiRakshak — HANDOFF PACKAGE for Phases 3 and 4
Packaged 2026-08-23. Phases 0, 1 and 2 are complete and verified.
================================================================================

WHAT THIS IS
  A Smart India Hackathon 2026 project. PS SIH26017, Ministry of Rural
  Development. "Predictive Analysis System for Early Detection of Land
  Acquisition Delays" — a government-internal dashboard that predicts which
  ongoing land acquisition projects will slip before they slip, names the
  statutory stage that will stall, explains each score with SHAP in officer
  language, and prescribes corrective action.

  Prototype evaluation: Thursday 2026-08-27.

WHAT IS NOT IN THIS ZIP
  .env                     — secrets. You must create your own; copy .env.example
                             and fill it. See SETUP below.
  .env.local-docker.bak    — secrets backup, deliberately excluded.
  .venv/                   — recreate it yourself.
  __pycache__/, .pytest_cache/ — build noise.

  EVERYTHING ELSE IS HERE: source, migrations, the eight dataset CSVs, the
  trained model artifacts, the docs, and the handover files.

--------------------------------------------------------------------------------
READ THESE FIRST, IN THIS ORDER
--------------------------------------------------------------------------------
  1. CLAUDE.md                          the operating contract. It governs
                                        everything. If a plan document
                                        contradicts it, CLAUDE.md wins.
  2. docs/handover/handover_phase_3.txt  the self-contained Phase 2 handover.
                                        Part C tells you exactly what Phase 3
                                        must build and how to consume the
                                        trained models. Read all of it.
  3. PROJECT_PLAN.md                     eight phases + the feature
                                        traceability matrix. Nothing in the
                                        problem statement has been dropped.
  4. PHASE_3_PROMPT.md                   a ready-to-paste prompt if you want to
                                        drive Phase 3 with an AI session.
  5. docs/research/dataset-audit.md      why the dataset looks the way it does.
  6. migrations/versions/                the schema you will read from.

--------------------------------------------------------------------------------
SETUP
--------------------------------------------------------------------------------
  Python 3.11. Verified library set: xgboost 2.1.4, shap 0.46.0,
  scikit-learn 1.5.2, pandas 2.2.3, numpy 2.0.2.

    python -m venv .venv
    .venv\Scripts\activate            (Windows)   or   source .venv/bin/activate
    pip install -r ml/requirements.txt
    pip install -r requirements-phase1.txt

  Copy .env.example to .env and fill it. At minimum you need:

    POSTGRES_HOST / POSTGRES_PORT / POSTGRES_DB / POSTGRES_USER / POSTGRES_PASSWORD
    DATABASE_URL=postgresql+psycopg://<user>:<pass>@localhost:5432/lade
    MODEL_REGISTRY_PATH=ml/experiments/registry
    ACTIVE_MODEL_VERSION=v2026-08-23T12-16-56

  Phase 3 additionally needs JWT_SECRET_KEY — generate with:
    openssl rand -hex 32

  Database:
    docker compose up -d db          (postgis/postgis:16-3.4)
    alembic upgrade head             (head is 0003)
    python scripts/seed.py           (add --truncate to re-run)

  There is also a shared Supabase dev DB. If you use it:
    - connect with the SESSION POOLER string (port 5432, *.pooler.supabase.com)
    - NEVER the direct connection (IPv6-only)
    - NEVER the transaction pooler (port 6543 — breaks prepared statements and DDL)
    - NEVER run `alembic downgrade base` against it; migration 0001's downgrade
      drops the PostGIS extension.
    Rationale: docs/design/adr-001-supabase-shared-dev-db.md

--------------------------------------------------------------------------------
VERIFY THE HANDOFF BEFORE YOU BUILD ANYTHING
--------------------------------------------------------------------------------
    python -m pytest ml/tests -q        expect 21 passed
    python scripts/verify_phase2.py     expect 10/10 PASS
    python scripts/verify_phase1.py     expect 17/17 PASS (needs a live DB)

  If verify_phase2 is not 10/10, stop and find out why before writing any
  backend code. The models are the product.

--------------------------------------------------------------------------------
WHAT IS ALREADY DONE
--------------------------------------------------------------------------------
  Phase 0 — foundation, dataset rev 3 (synthetic, 900 projects).
  Phase 1 — Postgres + PostGIS, three Alembic migrations, seed script.
            Seeded: 900 projects (600 closed / 300 ongoing), 768 admin_units,
            4,500 risk_history, 4,518 status_log, 927 succession_claims,
            362 succession_risk, 628 project_dependencies, 41 officers.
            risk_scores, risk_reasons, recommendations, alerts, annotations,
            audit_log are EMPTY — Phase 3/6/7 fill them.
  Phase 2 — Model A (XGBoost binary is_delayed): out-of-fold AUC 0.9212,
            accuracy 0.8567, isotonic-calibrated.
            Model B (XGBoost 5-class delay_stage, conditional on delay):
            accuracy 0.7127 vs 0.3470 majority baseline = 2.05x.
            ml/src/features/ is the single feature-definition module.
            ml/src/explainability/ is SHAP + the officer-language reason codes.
            Registry: ml/experiments/registry/v2026-08-23T12-16-56/
            Report card: ml/experiments/report_card_latest.md

--------------------------------------------------------------------------------
YOUR JOB: PHASE 3, THEN PHASE 4
--------------------------------------------------------------------------------
  PHASE 3 — Backend API + auth  (~6 h)
    FastAPI. Login with officer_id + password + CAPTCHA issuing a JWT with role
    and district claims. No registration route, ever. RBAC: admin unscoped,
    officer filtered to their own district on EVERY query. Seventeen endpoints
    (listed in handover_phase_3.txt §C4). Pydantic request AND response schema
    on every route. Audit middleware. A batch job scoring all 300 ongoing
    projects into risk_scores + risk_reasons.

    Exit criterion: Swagger at /docs lists every route; a Field Officer JWT
    returns 403 or an empty set for a project outside their district (asserted
    by a passing test); all 300 ongoing projects have a stored risk score and
    top-3 reasons.

  PHASE 4 — Frontend shell + Overview + Map  (~6 h)
    Vite + React 18. Auth context, JWT storage, protected routes, role-aware
    nav. Login page with CAPTCHA. Overview: summary cards, a Leaflet map with
    risk-coloured pins (red >= 0.70, amber 0.40-0.69, green < 0.40) clustered by
    district, and a sortable/filterable project table. Cascade filters
    State -> District -> Taluk -> Village.

    Exit criterion: an admin login shows all 300 ongoing projects on map and
    table; an officer login shows only their district's rows and no Analytics
    nav item; every map pin renders inside the correct district boundary.

--------------------------------------------------------------------------------
THINGS THAT WILL BITE YOU IF NOBODY TELLS YOU
--------------------------------------------------------------------------------
  1. status_log has NO cross-stage history. It records the desk chain within
     each project's CURRENT stage only — ~5 desks per project, not 5 stages.
     The SLA / stuck-file clock must be DESK-BASED, not stage-based. Do not
     promise a stage-duration chart; the data cannot support it.

  2. District polygons are DERIVED convex hulls of village centroids
     (district_boundaries.source = 'derived-village-hull'), not survey
     boundaries. Label them approximate in the UI and say so if a judge asks.

  3. projects.legal_dispute_stage contains the literal string "None", meaning
     "no dispute on file" — ordinal level 0, NOT a missing value.
     pandas.read_csv turns it into NaN and silently destroys the level.
     ml/src/features/build.py::load_projects() handles this. Do not "simplify"
     it away; there is a test that documents the bug.

  4. NEVER rebuild feature engineering in the backend. Import
     ml.src.features.build_feature_matrix and ALWAYS pass explainer.spec to it.
     Without the spec, one-hot levels are derived from whatever rows are in the
     request, the column order shifts, and the model silently scores garbage.

  5. Derived scores (compensation-gap index, litigation-propensity score,
     succession risk) are APPLICATION features. None is a model input.
     Succession risk is a deterministic rule — import
     ml.src.features.succession_risk, do not re-derive the thresholds. It is
     asserted equal to the seeded succession_risk table on all 362 parcels.

  6. Model B outputs class INDICES. Read the label order from
     metadata.json["delay_stage_classes"], never by sorting the labels.

  7. Risk bands are High >= 0.70, Medium 0.40-0.69, Low < 0.40. Recorded in
     metadata.json. The map pin colours must use these exact cut points.

  8. Do not retrain the models. If a retrain becomes unavoidable, run
     `python -m ml.src.training.train` then `python scripts/verify_phase2.py`
     and only accept the new version at 10/10. The stage model's margin is thin
     (2.05x against a 2.0x bar).

--------------------------------------------------------------------------------
HOW TO CALL THE MODELS
--------------------------------------------------------------------------------
  Load once at app startup, hold on app.state:

      from ml.src.explainability import RiskExplainer
      explainer = RiskExplainer.from_registry()      # reads ACTIVE_MODEL_VERSION

  Score projects fetched from Postgres:

      from ml.src.features import build_feature_matrix
      X, _ = build_feature_matrix(df, explainer.spec)     # PASS THE SPEC
      p    = explainer.calibrated_probability(X)          # -> risk_scores
      stg  = explainer.predict_stage(X)                   # -> delay stage

  Explain one project:

      exp = explainer.explain_project(row)                # dict or Series
      exp.to_dict(n=5)
      # factors carry: feature, value, shap_value, contribution_pct (signed),
      #                direction, group, display_label

  factor.display_label goes straight into risk_reasons.display_label.
  factor.group is the cluster label for the Phase 5 SHAP bar chart.

  Reference outputs to check your batch job against:
      ml/experiments/registry/<version>/ongoing_scores.csv    300 rows
      ml/experiments/registry/<version>/derived_scores.csv    900 rows

--------------------------------------------------------------------------------
NON-NEGOTIABLE CONVENTIONS
--------------------------------------------------------------------------------
  - Routers thin, services fat. No DB access outside backend/app/services/.
  - Every endpoint gets a Pydantic request AND response schema. No bare dicts.
  - Every foreign key indexed; every geometry column gets one GiST index.
  - Feature definitions live once, in ml/src/features/.
  - No TODO placeholders in committed code.
  - Secrets only in local .env, never committed.
  - Government-internal only. Two roles: admin, officer. Never add a
    citizen-facing surface, not even read-only.
  - ULPIN is the primary key. Settled — do not re-open it.
  - Training data is SYNTHETIC and must be described as such. No public
    land-acquisition delay-risk dataset exists in India, and that absence is
    the novelty argument, not a defect.
  - Absolute dates everywhere, never relative ones.

--------------------------------------------------------------------------------
HANDOVER PROTOCOL
--------------------------------------------------------------------------------
  At the end of EVERY phase, write docs/handover/handover_phase_X.txt with
  Part A (project summary + status + phase just completed), Part B (what the
  session did: decisions, files created/modified, blockers), Part C (a
  self-contained handoff a cold session can resume from, ending with the next
  phase's binary exit criterion). Update ## Current Phase in CLAUDE.md at the
  same time. Then stop and wait for confirmation before starting the next phase.

  A phase is done when its binary exit criterion is VERIFIED — not when work
  was done on it. Do not report a check as passing unless you ran it and saw
  the output.

================================================================================
