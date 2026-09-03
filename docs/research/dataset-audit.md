# Dataset Audit — land_acquisition_dataset.csv
Audited 2026-08-23. 300 rows x 40 columns.

**Verdict: good enough to build and demo on. Trains a real model. Five defects, all fixable in
roughly 3-4 hours, and two of them will be visible to judges if left alone.**

## Measured performance (5-fold CV, gradient-boosted trees, leakage column removed)

| Model | Result |
|---|---|
| `is_delayed` binary | **AUC 0.805**, accuracy 0.747 |
| `delay_stage` 3-class (delayed rows only, n=150) | **accuracy 0.780** vs 0.573 majority baseline |

Both are honest, demo-grade numbers. Do not quote higher.

## What is well built — keep it

- **ULPIN is internally correct.** State codes match Census 2011 (KA=29, TN=33, UP=09, OD=21,
  CG=22, TG=36, MH=27, MP=23) and the district code is constant within each district across all
  32 districts. 300 unique ids, no collisions. This holds up to inspection.
- **Officer IDs** follow the `KA-LAO-2023-0140` convention consistently.
- **Class balance** is exactly 150/150 on `is_delayed`.
- **Field vocabulary is LARR-accurate**: approval stages (SIA Completed → Section 11 Notification
  → Award Declared → Compensation Disbursement → Possession Taken → R&R Implementation),
  dispute stages, clearance statuses.

## Defect 1 — `delay_probability` is a leakage column (CRITICAL)

It is the generator's own scoring formula and correlates 0.79 with the label. **Drop it from the
feature matrix.** Left in, the model scores near-perfect and SHAP reports "delay_probability" as
the reason for delay — which is circular and a judge will spot it. Keep the column in the DB for
display; never feed it to the model.

## Defect 2 — coordinates do not match their districts (VISIBLE ON STAGE)

Latitude/longitude are drawn randomly across India, not from the district. Bengaluru Urban
projects span lat 11.59-18.33; Karnataka rows land in Tamil Nadu and Maharashtra. Two consequences:

1. **The Leaflet map will place pins in the wrong states.** Any judge from these eight states sees
   it immediately, and the map is a Core demo screen.
2. `longitude` currently ranks as the **8th most important feature** — the model is learning pure
   geographic noise.

Fix: a district-centroid lookup (32 districts) plus ±0.05° jitter. About 45 minutes.

## Defect 3 — 18 of 33 candidate features have literally zero importance

The generator wired only four real drivers: `compensation_disbursed_pct` (0.288),
`rehab_progress_pct` (0.235), `no_legal_disputes` (0.148), `days_since_dispute_filed` (0.043).

Everything below is dead weight — SHAP will show a flat zero bar for all of it:

`no_pending_clearances`, `no_ownership_disputes`, `ownership_dispute_flag`, `court_stay_flag`,
`compensation_dispute_flag`, `no_compensation_appeals`, `rehab_plan_approved_flag`,
`resettlement_site_ready_flag`, `title_clarity_status`, `legal_dispute_stage`, `approval_stage`,
`environmental_clearance_status`, `forest_clearance_status`, `project_type`, `state`, `district`,
`implementing_agency`, `is_closed_project`.

**This directly breaks three planned features:**

| Feature | Field it needs | Current importance |
|---|---|---|
| Litigation-propensity score | `no_ownership_disputes`, `title_clarity_status` | 0.002 / 0.000 |
| SLA / stuck-file clock | `days_in_current_stage` | 0.042 (corr +0.056) |
| Administrative-bottleneck driver | `no_pending_clearances` | 0.0025 |

The problem statement explicitly names *"pending approvals... incomplete documentation...
administrative bottlenecks"* as key delay drivers. As the data stands, **SHAP will never surface
any of them.** An officer would ask why, and the honest answer is "our data doesn't encode it".

Fix: re-inject correlations for approvals, title clarity, ownership disputes and stage-dwell into
the delay formula, then regenerate. ~1.5 hours, and it makes SHAP tell the story the PS asks for.

## Defect 4 — three companion tables are missing

| Missing | Blocks | Cost |
|---|---|---|
| `risk_history` — 4-6 timestamped snapshots per project | Recharts risk trend line (renders a single point) | ~45 min |
| `status_log` — desk-level entry/exit timestamps | SLA / stuck-file clock ("47 days at legal review") | ~45 min |
| `officers` — 8-10 seeded accounts with bcrypt hashes | JWT login; `assigned_field_officer_id` currently points at nothing | ~30 min |

Also absent: any circle-rate or market-value benchmark column, so the **compensation-gap index**
cannot be computed from this file. One extra column (`circle_rate_per_acre`) fixes it.

## Defect 5 — smaller issues

- `historical_delay_days` is populated only for the 132 closed projects. A days-slip regressor can
  train on those, but cannot be evaluated on ongoing ones. Present it as classification only, or
  scope the regressor to closed projects and say so.
- 178 of 300 rows have `expected_completion_date` already in the past as of today. For a system
  that predicts delay *before* it happens, an officer looking at an overdue project does not need a
  prediction. Shift the date distribution forward, or filter the "at-risk" view to future dates.
- 80 ongoing projects carry `is_delayed = True`. Decide whether the label means "already overdue"
  or "will become overdue", and say which. They are different products.
- `delay_stage` = "Not Applicable" for all 150 non-delayed rows, so the stage model is conditional
  on delay. Correct design, but the Legal Dispute class has only 31 examples — expect it to be the
  weakest of the three, and don't cherry-pick it for the demo.
- `title_clarity_status` is 220 Clear / 77 Partial / **3 Disputed**. Three rows cannot support any
  claim about disputed titles.

## Recommended fix order (≈3-4 hrs total)

1. Drop `delay_probability` from features — 5 min, and non-negotiable
2. District-centroid coordinates — 45 min (map correctness)
3. Re-inject correlations for approvals / title / ownership / stage-dwell + add
   `circle_rate_per_acre`, regenerate — 1.5 hrs (SHAP correctness)
4. Generate `risk_history`, `status_log`, `officers` — 2 hrs
5. Shift `expected_completion_date` distribution forward — 15 min

---

# Rev 2 — all five defects fixed (2026-08-23)

Regenerated by `ml/src/data/generate_dataset.py`. Old CSV superseded; do not train on it.

## Measured performance (5-fold CV on the 600 closed projects)

| Model | Rev 1 | **Rev 2** |
|---|---|---|
| `is_delayed` binary | AUC 0.805 | **AUC 0.907**, acc 0.810 |
| `delay_stage` | 3-class, 0.780 vs 0.573 base | **5-class, 0.588 vs 0.324 base** |

## What changed

| Defect | Fix |
|---|---|
| 1 — leakage | `delay_probability` gone. `latent_risk_audit` and `top_driver_audit` remain for debugging and are on the mandatory drop-list. |
| 2 — coordinates | District centroids + ±0.06° jitter. Max within-district spread now 0.34° (was 6.7°). Map pins land in the right district. |
| 3 — dead features | Delay formula now weights 12 drivers. Every field the problem statement names carries measurable importance. |
| 4 — missing tables | `risk_history.csv` (4,500 rows, 5 snapshots/project), `status_log.csv` (4,520 desk-level rows across 7 desks), `officers.csv` (41 accounts: 32 LAOs + 8 Collectors + 1 nodal). New columns `circle_rate_per_acre_lakhs`, `compensation_fair_value_lakhs`, `compensation_gap_pct`, `ownership_fragmentation_index`. |
| 5 — label meaning | 600 **closed** projects carry `is_delayed` / `delay_stage` / `historical_delay_days` and are the training set. 300 **ongoing** projects have those fields null, all completion dates in the future, and are what the system scores. The label now means "will become overdue". |

## Feature importance, rev 2 (ordinal-encoded, GBM)

```
no_legal_disputes            0.259     legal_dispute_stage      0.071
compensation_disbursed_pct   0.139     title_clarity_status     0.057
compensation_gap_pct         0.123     days_since_dispute_filed 0.047
no_ownership_disputes        0.091     days_in_current_stage    0.022
                                       no_pending_clearances    0.016
```

Compensation gap, ownership disputes, title clarity, stage dwell and pending clearances all
register — so SHAP can now show what the PS asks it to show.

## Two rules for the training script

1. **Mandatory drop-list.** Never feed the model: `ulpin`, `project_name`, `latent_risk_audit`,
   `top_driver_audit`, `is_delayed`, `delay_stage`, `historical_delay_days`,
   `actual_completion_date`, `assigned_field_officer_id`, `notification_date`,
   `expected_completion_date`, `is_closed_project`, `planned_duration_days`.
2. **Encode ordinals explicitly.** `cat.codes` alphabetical ordering flattens
   `title_clarity_status` and `legal_dispute_stage` to zero importance. Use:
   - title: Clear 0, Partial 1, Disputed 2
   - dispute stage: None 0, Resolved 1, Filed 2, Under Hearing 3, Stayed by Court 4
   - clearances: Not Required/Obtained 0, Applied 1, Pending 2
   - approval stage: Possession Taken 0 … SIA Completed 5 (exposure order)
   - one-hot `project_type`, `implementing_agency`, `state`, `district`

## Login accounts (demo)

`officers.csv` username = `officer_id` (e.g. `KA-LAO-2023-0140`, `TN-DC-2019-0012`).
Demo password = officer_id lowercased; `password_sha256_demo` is a placeholder — **replace with
bcrypt at seed time**, do not ship SHA-256 password storage.

---

# Rev 3 — the three plan gaps closed (2026-08-23)

Nothing in PROJECT_PLAN.md is now blocked on missing data.

## New performance (5-fold CV, 600 closed projects, ordinal-encoded GBM)

| Model | Rev 1 | Rev 2 | **Rev 3** |
|---|---|---|---|
| `is_delayed` binary | AUC 0.805 | AUC 0.907 | **AUC 0.925**, acc 0.848 |
| `delay_stage` | 3-class 0.780 / 0.573 | 5-class 0.588 / 0.324 | **5-class 0.679 / 0.347** |

The stage model improved because project pins now sit at real village coordinates instead of
random ones, so latitude/longitude stopped injecting noise.

## New files

**`admin_units.csv`** — 768 rows. State → District → Taluk → Village, with `village_code`,
`ri_circle`, `revenue_inspector`, `tehsildar`, `no_plots`, `no_khatiyans`, `no_tenants`.
Feeds both the cascade dropdown and the statistics panel.

National totals for the panel: 8 states · 32 districts · 128 tehsildars · 768 villages ·
256 RI circles · 2,293,187 plots · 1,612,419 khatiyans · 573,899 tenants.

**`succession_claims.csv`** — 927 heir claims over 362 parcels. Columns: `claim_id`, `ulpin`,
`claimant_name`, `relation_to_recorded_owner`, `blood_relation`, `proof_status`,
`proof_document`, `claimed_share_pct`, `verification_status`, `claim_filed_on`.

**`succession_risk.csv`** — the rule output per parcel: claim count, undocumented count,
contested count, total claimed share, band, reason.

**`project_dependencies.csv`** — 628 edges for cascading impact. Synthetic by construction.

## ULPIN is now fully grounded

The 14-digit id decomposes correctly against `admin_units` at **100%** on all three segments:

```
36 - 027 - 018 - 816317
│     │     │      └── parcel serial
│     │     └───────── village code, matches admin_units.village_code
│     └─────────────── district code, matches admin_units.district_code
└───────────────────── Census 2011 state code
```

Coordinates are now drawn from village centroids (±0.012°), not district centroids, so a pin sits
in the right village, not merely the right district.

## Bloodline proof — implementation note

**This is an application feature, not a model input.** No succession column is fed to XGBoost.
The risk band is a deterministic rule, implemented identically in `generate_dataset.py`
(`succession_risk()`) and to be reimplemented in the backend service:

| Band | Condition |
|---|---|
| High | any contested claim, **or** claimed shares total > 105% of the parcel |
| Medium | any undocumented claim, **or** more than 2 heirs on one parcel |
| Low | every heirship claim documented |

Current spread: 134 High / 167 Medium / 61 Low.

Because it is a rule, it always yields a stated reason — *"3 heir claims without documentary proof
— mutation not established"* — which is what the Project Detail succession panel renders. The
proof documents are real instrument names (Registered Will, Mutation Entry (RoR), Legal Heir
Certificate, Succession Certificate, Partition Deed; Panchayat attestation and unverified
affidavits on the undocumented side).
