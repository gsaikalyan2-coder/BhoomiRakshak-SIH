# Scope of Record — BhoomiRakshak (LADE)
Rev 2, 2026-08-23. Supersedes rev 1. Source of truth: SIH_PS_PLAN_VERSION.pdf, reconciled with
the expand-and-contract pass. Demo target: end-to-end thin slice, real Postgres+PostGIS, nothing faked.

## Decisions locked this session
- **Name:** BhoomiRakshak
- **PDF governs** where it conflicted with rev 1; six PDF-only features re-enter scope
- **ULPIN retained** as the project primary key (user decision, 2026-08-23). The working
  dataset's ULPINs are internally consistent — Census 2011 state codes, stable district codes,
  300 unique ids. Settled; not to be revisited.
- **Government-only.** No citizen layer, not even read-only
- **Real PostgreSQL + PostGIS**, not CSV/pandas
- **CAPTCHA retained** on the login page (user decision, against the PDF's typed argument)
- **Real SMTP alerts**, not simulated
- Kept from rev 1 despite absence from the PDF: compensation-gap index, litigation-propensity score
- Dropped from rev 1: silent-project detector, intervention feedback loop

## Build order — cut from the bottom, decide by Wednesday evening

| # | Item | Est | Band |
|---|---|---|---|
| 0 | Schema + synthetic generator (projects, risk_history, status_log, officers) | 4h | Foundation |
| 1 | JWT auth, admin/field-officer roles, CAPTCHA, seeded accounts | 3h | Must |
| 2 | Model A — `is_delayed` binary XGBoost | 2h | Must |
| 3 | Model B — `delay_stage` multi-class | 1.5h | Must |
| 4 | Engineered features: compensation-gap index, litigation-propensity | 1.5h | Must |
| 5 | SHAP TreeExplainer + top-3 reason codes API | 2h | Must |
| 6 | FastAPI: /login /projects /projects/{id} /shap /recommend /predict | 4h | Must |
| 7 | React shell, auth guard, routing | 3h | Must |
| 8 | Overview screen: summary cards + sortable project table | 3h | Must |
| 9 | Project detail: risk score, Recharts trend line, SHAP bar chart | 4h | Must |
| 10 | Leaflet map, risk-coloured pins, district clustering | 3h | Must |
| 11 | Rule-based recommendation engine | 2h | Must |
| 12 | Flan-T5 narrative wrapper on recommendations | 2.5h | Should |
| 13 | What-if simulator slider | 2h | Should |
| 14 | SLA / stuck-file clock | 1.5h | Should |
| 15 | Alerts: SMTP send + alerts panel | 1.5h | Should |
| 16 | Admin annotation ("action taken") + audit log | 2h | Should |
| 17 | District risk heatmap + state statistics panel | 2.5h | Should |
| 18 | Weekly auto-generated district brief (Flan-T5) | 2h | Should |
| 19 | NL query interface (intent-match + SQL template, NOT RAG) | 3h | Stretch |
| 20 | Cross-project benchmarking | 2h | **Sacrificial** |
| 21 | Cascading impact awareness | 3h | **Sacrificial** |
| 22 | Light/dark mode, About page, i18n | 2h | **Sacrificial** |
| 23 | Demo prep: seed check, backup video, deck | 4h | Must |

**Total ≈ 66h against ~45-50 realistic person-hours for two people over three days.**
The sacrificial band (20-22) is 7h. Cutting it still leaves ~59h. See watch-out 1.

## OUT — explicitly not doing
- Any citizen or public surface, ever
- ULPIN as an identifier
- Silent-project detector; intervention feedback loop (dropped rev 1 items)
- Officer-workload feature; LACRRIS/Bhoomi Rashi ingest adapters; objection-text NLP
- Drift monitoring / retrain automation; full RAG for the NL query
- User-management UI, self-registration, password reset

## Watch-outs
1. **The plan is ~15-20 hours over budget even after cutting the sacrificial band.** Two more
   items must go. Cheapest honest cuts, in order: #21 cascading impact (needs a dependency graph
   that does not exist in your data), #20 benchmarking, #22 theming. If still over, #18 weekly
   brief folds into #12 — same Flan-T5 call, different prompt template.
2. **#19 NL query is worth more than #20+#21 combined.** It is a headline novelty in the PDF and
   costs 3h as intent-matching + SQL templating. Protect it above the two items ranked below it.
3. **Delay-stage prediction (#3) needs a `delay_stage` label in the generator**, with realistic
   class balance. If the generator produces near-uniform stages, the multi-class model will look
   random on stage and undercut the feature it exists to sell. Build the label deliberately.
4. **CAPTCHA is domain-inaccurate for an internal departmental portal** and the PDF's own typed
   section argues against it. Retained by decision. If a judge challenges it, the honest answer
   is "defence in depth", not "real portals do this".
5. **Risk trend lines need `risk_history`** — 4-6 timestamped snapshots per project. The PDF flags
   this as a known gap. Without it #9's trend chart has one point and looks broken.
