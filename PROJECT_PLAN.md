# PROJECT_PLAN.md — BhoomiRakshak

**Predictive Analysis System for Early Detection of Land Acquisition Delays**
SIH 2026 · PS **SIH26017** · Ministry of Rural Development · Software · Agriculture & Foodtech

Plan of record. Written 2026-08-23. Governed by `CLAUDE.md`; scope of record in
`docs/design/scope.md`. Where this document and `CLAUDE.md` disagree, `CLAUDE.md` wins.

**Prototype evaluation: Thursday 2026-08-27.** Three build days: Mon 24, Tue 25, Wed 26 Aug.

---

## 1. Goal

Shift land acquisition governance from reactive reporting to proactive early intervention.
The system scores every ongoing acquisition for delay risk *before* the delay materialises,
names the statutory stage that will stall, explains the score factor-by-factor, prescribes a
corrective action, and lets the officer test that action before taking it.

**Government-internal only.** Two roles: Admin (District Collector / State Nodal Officer) and
Field Officer (SDM / Land Acquisition Officer). No citizen surface, no public registration.

---

## 2. Locked decisions

These are settled. Do not re-open them mid-build.

| Decision | Value |
|---|---|
| Product name | **BhoomiRakshak** |
| Project primary key | **ULPIN**, 14-digit DILRMP format `29-007-760-288390` |
| Officer ID | `TN-LAO-2024-0456` (field) / `TN-DC-2019-0012` (admin) |
| Audience | Government only — no citizen layer, not even read-only |
| Database | **Real PostgreSQL 16 + PostGIS 3**, not CSV/pandas |
| Login | Username + password + **CAPTCHA** (retained by user decision) |
| Alerts | **Real SMTP email** on threshold breach, with logged in-app fallback |
| Label meaning | "**will become overdue**" — train on 600 closed, score 300 ongoing |
| Roles | Exactly 2: `admin`, `officer`. Auditor role only if Phase 8 runs early. |
| Governing spec | `SIH PS PLAN VERSION.pdf`, reconciled 2026-08-23 |

---

## 3. Feature traceability matrix

Every feature named in the PDF or stated explicitly by the user, and the phase that delivers it.
**Nothing in the PDF has been dropped.**

### 3.1 The ten novelty features (PDF §"Unique features")

| # | Feature | Phase | Deliverable |
|---|---|---|---|
| N1 | Predictive risk score (not just tracking) | 2 | `is_delayed` XGBoost, calibrated probability per project |
| N2 | Explainable AI via SHAP | 2 | TreeExplainer, top-N factor contributions with % |
| N3 | Delay-stage prediction | 2 | 5-class model: Compensation / Legal / R&R / Ownership-Title / Administrative |
| N4 | Actionable recommendations | 6 | Rule map keyed on SHAP factors + Flan-T5 narrative |
| N5 | What-if simulator | 6 | Slider re-calls `/predict` with modified inputs, live re-score |
| N6 | Natural-language query interface | 6 | Intent match + SQL template (explicitly **not** RAG) |
| N7 | SLA / stuck-file clock | 5 | Days at current desk from `status_log`, "at Legal Cell 47 days" |
| N8 | Cross-project benchmarking | 7 | Peer cohort by state + project type + area band |
| N9 | Cascading impact awareness | 7 | ✅ Data ready — `project_dependencies.csv`, 628 edges |
| N10 | Weekly auto-generated risk brief | 6 | Flan-T5 one-paragraph district summary for the Collector |

### 3.2 Extra features (PDF handwritten §"Extra features")

| # | Feature | Phase |
|---|---|---|
| E1 | Delay-stage prediction, shown per stage not as one number | 2, 5 |
| E2 | **Resolution timeline** — if issues are sorted, show *when*, from land filing to approval | 1, 5 |
| E3 | Auto-generated weekly risk brief per district (Flan-T5) | 6 |
| E4 | Track how long a file has sat at each desk (LAO, Registration, …) | 1, 5 |

### 3.3 Dashboard screens (PDF §"What the dashboard should have")

| Screen | Element | Phase |
|---|---|---|
| **Overview (Admin)** | Summary cards: total projects, high/medium/low risk counts, escalated this week | 4 |
| | Leaflet map, pins red/amber/green, clustered by district | 4 |
| | Sortable + filterable table: name, district, risk score, top risk factor, days stuck | 4 |
| **Project Detail (both roles)** | Header: name, location, stage, timeline start → expected completion | 5 |
| | Risk score + Recharts trend line (improving or worsening) | 5 |
| | SHAP horizontal bar chart, factors pushing risk up/down | 5 |
| | Recommended actions (rule-based + LLM narrative) | 6 |
| | SLA clock — "stuck at legal review for 47 days" | 5 |
| | Officer's own update form (compensation %, rehab, dispute status) — **Field Officer only** | 5 |
| **Analytics (Admin only)** | District-wise risk heatmap | 7 |
| | "Similar project benchmark" comparison | 7 |
| | Weekly auto-generated brief | 6 |
| **Alerts panel** | Recent threshold-breach alerts, "sent to Officer X" | 7 |

### 3.4 RBAC (PDF §"Role-Based Access Control")

| Requirement | Phase |
|---|---|
| Admin sees all projects across districts/states | 3 |
| Admin views risk scores, SHAP, recommendations | 3, 5 |
| Admin can override/annotate a risk flag ("action taken", "escalated to legal cell") | 7 |
| Admin gets state-wide trend analytics + weekly brief | 6, 7 |
| Field Officer sees only their district/jurisdiction | 3 |
| Field Officer can update project status — the data-entry role that feeds the model | 5 |
| Field Officer sees risk + recommendations for their projects only, not ministry analytics | 3, 5 |
| Optional Auditor/Viewer read-only role | 8 (only if ahead of schedule) |
| Seeded demo accounts, JWT role claim, gated routes and UI, **no user-management UI** | 3 |

### 3.5 Handwritten-page requirements

| Requirement | Phase | Note |
|---|---|---|
| Admin cascade dropdowns: State → District → Taluk → Village | 4 | ✅ Data ready — `admin_units.csv`, 768 villages / 128 taluks |
| **Bloodline / succession proof** — heir risk, blood relation with proof vs without | 3, 5 | ✅ Data ready — `succession_claims.csv`. **Application feature, not a model input** |
| One field officer per district | 1 | Already satisfied: `officers.csv` has 32 district LAOs |
| Dept login: username + password + CAPTCHA | 3 | |
| State statistics panel: districts, tehsildars, villages, RI circles, plots, tenants, khatiyans | 7 | ✅ Data ready — live aggregate over `admin_units` |
| Languages (i18n) | 8 | English + Hindi strings only |
| Light / dark mode | 8 | |
| "About this portal" page | 8 | |
| Exactly two roles: admin, field officer | 3 | |

### 3.6 Features the user added beyond the PDF

| Feature | Phase | Rationale |
|---|---|---|
| Compensation-gap index (offered vs circle rate → refusal risk) | 2 | Already generated: `compensation_gap_pct`, importance 0.123 |
| Litigation-propensity score (fragmentation + title clarity) | 2 | Already generated: `ownership_fragmentation_index`, importance 0.091 |

---

## 4. Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  React 18 + Vite                                                 │
│  Overview · Project Detail · Analytics · Alerts · About          │
│  Recharts (trends, SHAP bars) · Leaflet (pins, heatmap)          │
└───────────────────────────┬──────────────────────────────────────┘
                            │ JWT (role + district claims)
┌───────────────────────────▼──────────────────────────────────────┐
│  FastAPI                                                         │
│  routers (thin) → services (all logic) → SQLAlchemy              │
│  middleware: auth · RBAC scoping · audit log                     │
└──────┬─────────────────────┬──────────────────┬──────────────────┘
       │                     │                  │
┌──────▼───────┐  ┌──────────▼─────────┐  ┌─────▼──────────────────┐
│ PostgreSQL   │  │ Model serving      │  │ Intelligence           │
│ + PostGIS    │  │ XGBoost binary     │  │ rule map → Flan-T5     │
│ projects     │  │ XGBoost 5-class    │  │ what-if · NL query     │
│ risk_history │  │ SHAP TreeExplainer │  │ weekly brief           │
│ status_log   │  └────────────────────┘  └────────────────────────┘
│ officers …   │
└──────────────┘
```

---

## 5. Phases

Each phase ends with a handover file per the project protocol (§6). **Do not start a phase until
the user confirms receipt of the previous handover.**

---

### Phase 0 — Foundation *(COMPLETE)*

**Objective.** Repository, conventions, competitive research, scope, working dataset.

**Delivered.** Folder tree; `CLAUDE.md`; `FOLDER_STRUCTURE.md`; `docker-compose.yml`; Dockerfiles;
requirements; CI; `docs/research/competitive-landscape.md`;
`docs/research/gap-coverage-matrix.md`; `docs/research/dataset-audit.md`; `docs/design/scope.md`;
`ml/src/data/generate_dataset.py`; and the full dataset (rev 3):

| File | Rows |
|---|---|
| `projects.csv` | 900 — 600 closed (training) / 300 ongoing (scored) |
| `admin_units.csv` | 768 villages · 128 taluks · 256 RI circles · 32 districts |
| `risk_history.csv` | 4,500 — 5 snapshots per project |
| `status_log.csv` | 4,518 desk-level entries across 7 desks |
| `succession_claims.csv` | 927 heir claims over 362 parcels |
| `succession_risk.csv` | rule-based band + reason per parcel |
| `project_dependencies.csv` | 628 edges |
| `officers.csv` | 41 — 32 LAOs, 8 Collectors, 1 nodal |

**Exit criterion.** ✅ Met — **binary AUC 0.925, accuracy 0.848**; 5-class stage accuracy **0.679**
vs 0.347 majority baseline; every documented delay driver carries non-zero importance; ULPIN
state, district and village codes 100% consistent with `admin_units`; every project pin falls
inside its own district.

---

### Phase 1 — Data layer · *Mon 24 AM · ~5 h*

**Objective.** Real Postgres+PostGIS holding the full domain, including the three data gaps in §7.

**Deliverables.**
1. Alembic migrations creating: `projects`, `risk_history`, `status_log`, `officers`,
   `admin_units`, `succession_claims`, `project_dependencies`, `risk_scores`, `risk_reasons`,
   `recommendations`, `alerts`, `annotations`, `audit_log`.
2. PostGIS enabled; `geom` Point column on `projects` populated from lat/long; GiST index.
   District boundary GeoJSON loaded for the choropleth.
3. `issue_resolutions` view (E2): for each project, the date each issue class — notification,
   objection, award, compensation, R&R, possession — was cleared, or NULL if open. Derived from
   `status_log` + project stage dates.
4. `scripts/seed.py` loading all eight CSVs; officer passwords hashed with **bcrypt**
   (the shipped `password_sha256_demo` column is a placeholder and must not be used).
5. Index on every foreign key.

*(The three data gaps flagged in the first draft of this plan are now closed — see §7.)*

**Exit criterion.** `docker compose up` starts a healthy DB; `python scripts/seed.py` loads
900 projects, 4,500 history rows, 4,520 status rows, 41 officers, 32 admin units with counts;
`SELECT ST_AsText(geom) FROM projects LIMIT 1` returns a point inside its own district;
succession and taluk/village columns are non-null for every row.

---

### Phase 2 — ML core · *Mon 24 PM · ~5 h*

**Objective.** Both models trained, explained, versioned, and callable offline.

**Deliverables.**
1. `ml/src/features/` — single feature-definition module imported by both training and serving.
   Enforces the **mandatory drop-list** and the **explicit ordinal encodings** from
   `docs/research/dataset-audit.md` §"Two rules".
2. Model A — XGBoost binary `is_delayed`, trained on the 600 closed projects only.
3. Model B — XGBoost 5-class `delay_stage`, conditional on delay.
4. Derived scores computed and stored per project: **compensation-gap index**,
   **litigation-propensity score**, **succession risk**.
5. `ml/src/explainability/` — `shap.TreeExplainer`; function `project_row → top-N factors with
   signed contribution %`; a reason-code map translating feature names to officer language
   ("`compensation_gap_pct` → *Compensation offered is 34% below the circle-rate benchmark*").
6. `ml/src/evaluation/` — CV report card written to `ml/experiments/`: AUC, accuracy, confusion
   matrix, per-state slice, calibration curve.
7. Artifacts written to the registry with a version string; `ACTIVE_MODEL_VERSION` set in `.env`.

**Exit criterion.** `python -m ml.src.training.train` produces two versioned artifacts and a
report card showing **AUC ≥ 0.85** and **stage accuracy ≥ 2× the majority baseline**; the SHAP
function returns sensible top-3 factors for three hand-picked projects; no drop-list column
appears in the feature matrix (asserted by a unit test).

---

### Phase 3 — Backend API + auth · *Mon 24 evening → Tue 25 AM · ~6 h*

**Objective.** Every screen's data reachable, correctly scoped by role.

**Deliverables.**
1. `POST /api/v1/auth/login` — officer_id + password + **CAPTCHA token**; issues JWT with
   `role` and `district` claims. `POST /auth/captcha` returns a challenge. No registration route.
2. RBAC dependency: admin unscoped; officer filtered to their district on **every** query.
3. Endpoints:
   `GET /projects` (filter, sort, paginate) · `GET /projects/{ulpin}` ·
   `GET /projects/{ulpin}/shap` · `GET /projects/{ulpin}/recommend` ·
   `GET /projects/{ulpin}/history` · `GET /projects/{ulpin}/timeline` (E2) ·
   `GET /projects/{ulpin}/sla` (N7) · `GET /projects/{ulpin}/peers` (N8) ·
   `GET /projects/{ulpin}/downstream` (N9) · `PATCH /projects/{ulpin}` (officer update form) ·
   `POST /predict` (what-if, N5) · `GET /analytics/districts` · `GET /analytics/statistics` ·
   `GET /analytics/brief` (N10) · `GET /alerts` · `POST /annotations` · `GET /admin-units`
4. Pydantic request **and** response schemas on every route. No bare dicts.
5. Audit middleware: every state-changing call and every score served writes to `audit_log`.
6. Batch scoring job: score all 300 ongoing projects, write `risk_scores` + `risk_reasons`.

**Exit criterion.** Swagger UI at `/docs` lists every route above; a Field Officer JWT returns
**403 or an empty set** for a project outside their district (asserted by a test); all 300
ongoing projects have a stored risk score and top-3 reasons.

---

### Phase 4 — Frontend shell + Overview + Map · *Tue 25 PM · ~6 h*

**Objective.** Login works and the Admin overview screen is complete.

**Deliverables.**
1. Vite + React app, auth context, JWT storage, protected routes, role-aware navigation.
2. Login page with CAPTCHA. Two seeded accounts shown on screen for demo convenience.
3. Overview: summary cards (total, high/medium/low counts, escalated this week).
4. Leaflet map — risk-coloured pins (red ≥0.70, amber 0.40–0.69, green <0.40), district clustering,
   click-through to Project Detail.
5. Project table — sortable and filterable on name, district, risk score, top risk factor,
   days stuck. Field Officer sees only their district's rows.
6. Cascade filters: State → District → Taluk → Village, driven by `/admin-units`.

**Exit criterion.** Logging in as `TN-DC-…` shows all 300 ongoing projects on map and table;
logging in as `KA-LAO-…` shows only Karnataka-district rows and no Analytics nav item; every
map pin renders inside the correct district boundary.

---

### Phase 5 — Project Detail + officer update · *Wed 26 AM · ~6 h*

**Objective.** The screen the whole pitch rests on.

**Deliverables.**
1. Header — project name, location, current stage, timeline start → expected completion.
2. Risk score with band, plus **predicted delay stage** displayed as its own statement
   ("At risk *at the Compensation Disbursal stage*"), per E1.
3. Recharts risk trend line from `risk_history` — 5 points, rising or falling.
4. Recharts horizontal SHAP bar chart — factors pushing risk up and down, in officer language.
5. **SLA / stuck-file clock (N7)** — current desk and days there, with the full desk history.
6. **Resolution timeline (E2)** — every issue class with its clearance date, or "open".
7. Officer update form — compensation %, rehab progress, dispute status. **Field Officer only.**
   On save: re-score, write `audit_log`, refresh the trend line.

**Exit criterion.** Opening a high-risk project shows a non-flat trend line, at least three SHAP
factors, a named stuck desk with a day count, and a populated resolution timeline. Submitting the
officer form changes the stored risk score and appends an audit row.

---

### Phase 6 — Intelligence layer · *Wed 26 midday · ~7 h*

**Objective.** The four features that separate this from a dashboard.

**Deliverables.**
1. **Rule-based recommendation engine (N4)** — deterministic map from SHAP factor → action, each
   with an owner desk and an SLA. Runs first and always; never depends on the LLM.
2. **Flan-T5 narrative (N4)** — templated prompt taking the rule output + top SHAP factors, emits
   one officer-readable paragraph. Cached per project. **Falls back to the rule text on any
   model error** — the demo must not depend on a live inference call succeeding.
3. **What-if simulator (N5)** — sliders for compensation %, rehab %, dispute count; re-calls
   `/predict`; shows before → after risk with the delta.
4. **NL query interface (N6)** — intent classifier over a fixed set (at-risk-in-district,
   why-is-X-risky, stuck-at-stage, what-should-I-do, compare-with-peers, summarise-week) mapped to
   parameterised SQL. Not RAG. Unmatched queries return a helpful "try one of these" list.
5. **Weekly auto-generated district brief (N10/E3)** — Flan-T5 one-paragraph summary per district
   for the Collector, from that week's high-risk projects.

**Exit criterion.** Each of the six NL intents returns a correct answer from a typed question;
moving the compensation slider from 30% to 80% visibly lowers the risk score; the recommendation
panel renders even with the LLM disabled; the weekly brief names real projects and real drivers.

---

### Phase 7 — Analytics, alerts, governance · *Wed 26 PM · ~6 h*

**Objective.** The Collector's screens, and the accountability story.

**Deliverables.**
1. District-wise risk **heatmap** — PostGIS district polygons, choropleth by mean risk.
2. **State statistics panel** — districts, tehsildars, villages, RI circles, plots, tenants,
   khatiyans, from `admin_units`.
3. **Cross-project benchmarking (N8)** — peer cohort by state + project type + land-area band;
   "comparable acquisitions cleared this stage in X days on average; this one is at Y".
4. **Cascading impact (N9)** — `project_dependencies` edges; a high-risk project lists the
   downstream projects it puts at risk, with a badge on the Overview table.
5. **Alerts (real SMTP)** — threshold breach at `ALERT_RISK_THRESHOLD` sends email to the assigned
   officer and writes an `alerts` row. On SMTP failure, log and show the in-app banner.
   Alerts panel lists recent breaches with "sent to Officer X".
6. **Admin annotation** — "action taken", "escalated to legal cell", free note. Writes
   `annotations` + `audit_log`, and shows on the project detail.

**Exit criterion.** The heatmap shades all eight states; one real email arrives in a real inbox
from a threshold breach; an admin annotation persists and appears in the audit log; at least one
project displays a downstream dependency.

---

### Phase 8 — Polish, i18n, demo prep · *Wed 26 evening · ~5 h*

**Deliverables.**
1. **Light/dark mode** toggle, persisted.
2. **Languages** — English + Hindi string tables for navigation, labels, risk bands.
3. **"About this portal"** page — the problem, the approach, the honest limits from
   `docs/research/gap-coverage-matrix.md` §"The two honest limits".
4. Auditor/Viewer read-only role — **only if Phase 7 finished early**.
5. Empty/error/loading states on every screen; nothing renders a raw stack trace.
6. **Demo prep** — seeded scenario walkthrough, three hand-picked showcase projects (one
   compensation-driven, one litigation-driven, one succession-driven), **backup screen recording**,
   pitch deck aligned to `gap-coverage-matrix.md`.

**Exit criterion.** A cold `docker compose up` + seed + login reproduces the full demo path with
no manual intervention; the backup recording exists; the deck opens on N1 (predictive score) and
closes on the two honest limits.

---

## 6. Handover protocol

At the end of **every** phase, produce `docs/handover/handover_phase_X.txt` containing:

- **Part A — Project summary.** Goal, current status, which phase just completed.
- **Part B — Session summary.** What was accomplished, key decisions, files created/modified,
  blockers and unresolved issues.
- **Part C — Handoff.** Everything a cold session needs to resume with no chat history: locked
  decisions, environment state, what to do next, exit criterion of the next phase.

Then **stop and wait for the user to confirm receipt** before starting the next phase.
Update `## Current Phase` in `CLAUDE.md` at the same time.

---

## 7. Known gaps and risks

**All three data gaps are closed (dataset rev 3, 2026-08-23).** No feature in this plan is now
blocked on missing data.

| Was blocked | Resolved by | Detail |
|---|---|---|
| Taluk/village cascade; statistics panel | `admin_units.csv` | 768 villages, 128 taluks, 256 RI circles, 32 districts, 8 states, with per-village plots / khatiyans / tenants. ULPIN state, district **and village** codes now verified consistent against it at 100%. |
| Bloodline / succession proof | `succession_claims.csv`, `succession_risk.csv` | 927 heir claims across 362 parcels: relation, blood-relation flag, proof status (Documented / Undocumented / Contested), the actual proof document, claimed share %, verification status. |
| Cascading impact | `project_dependencies.csv` | 628 edges — contiguous stretches within a state and project type, plus corridor→feeder-road links. **Synthetic by construction; describe it as such.** |

**Bloodline proof is an application feature, not a model input.** It is never trained and none of
its columns is fed to XGBoost. The risk band is a deterministic rule, implemented identically in
the generator and in the backend service:

- **High** — any contested claim, or claimed shares summing above 105% of the parcel
- **Medium** — any undocumented claim, or more than two heirs on one parcel
- **Low** — every heirship claim documented

Current distribution: 134 High, 167 Medium, 61 Low. Because the rule is deterministic it always
produces a stated reason ("*3 heir claims without documentary proof — mutation not established*"),
which is what the Project Detail succession panel displays.

**Risk 1 — the schedule is the real constraint.**
Phases 1–8 total **≈46 hours** against roughly 45–50 realistic person-hours for two people over
three days. There is no slack. Nothing here is padding, so a slip means a feature is at risk, and
the PDF's instruction is that none may be dropped. **Mitigation:** phases 6 and 7 are the ones
that will squeeze. If Wednesday morning arrives with Phase 5 unfinished, the honest move is to
reduce depth rather than remove a feature — e.g. cascading impact as a static badge instead of a
graph view, benchmarking as a single comparison line rather than a chart. Every feature stays
present; some are shallower. Decide this Wednesday 09:00, not Wednesday 23:00.

**Risk 2 — Flan-T5 is the only live-inference dependency.**
It powers N4's narrative, N6's phrasing and N10's brief. All three must degrade to deterministic
rule/template output on failure. Build the fallback first, the LLM second.

**Risk 3 — training data is synthetic.**
Say it before a judge asks. No public land-acquisition delay-risk dataset exists in India — that
absence *is* the novelty argument. The generator is grounded in LARR Act 2013 parameters and
DILRMP/ULPIN structure with correlations deliberately injected, and the two fields no government
schema captures (circle-rate gap, ownership fragmentation) are a deployment recommendation, not a
defect.

---

## 8. Day map

| Day | Phases | Ends with |
|---|---|---|
| **Mon 24** | 1 Data layer · 2 ML core · 3 Backend (start) | Models trained, DB seeded, API skeleton |
| **Tue 25** | 3 Backend (finish) · 4 Frontend + Map | Login works, Overview screen complete |
| **Wed 26** | 5 Detail · 6 Intelligence · 7 Analytics · 8 Polish | Full demo path rehearsed, backup recorded |
| **Thu 27** | — | **Prototype evaluation** |
