# Competitive Landscape — Land Acquisition Monitoring in India
Compiled 2026-08-23. Sources listed at the end.

## 1. LACRRIS (larr.dolr.gov.in) — DoLR, Ministry of Rural Development
**What it is:** the statutory data-entry and reporting system for LARR Act 2013 acquisitions.
**Modules:** Project, Timeline, Reference Letter, Compensation, Administrator.
**Data captured:** dates under Sec. 4, 11, 19, 23, 38; compensation date; extent (ha/acre);
rural/urban flag; affected-family counts; payment data; scanned reference letters.
**Roles:** DoLR admin, central ministry officer, state/UT officer, public (reports only).
**Weaknesses**
- Pure **date-stamping after the fact** — a stage is recorded once it has already happened.
- **No forecasting, no risk scoring, no analytics beyond counts/charts** (the official user
  manual describes report generation only).
- Data quality is entry-dependent; a stalled project simply stops producing rows, so silence
  is indistinguishable from progress.
- No dispute/litigation, objection-volume, or R&R-friction fields — the actual delay drivers
  are not modelled at all.
- No geospatial layer; no parcel-level granularity.

## 2. PAIMANA (paimana-proj.mospi.gov.in) — MoSPI, replaced OCMS-2006
**What it is:** central monitoring of infrastructure projects ≥ ₹150 cr. As of Dec 2025:
1,392 projects, ₹29.68 lakh cr sanctioned cost.
**Strengths:** "One Data One Entry", API integration with IPMP across 17 ministries (~60% of
projects auto-update), automated flash reports on cost escalation and time overruns.
**Weaknesses**
- **Retrospective by design.** It reports overruns that already occurred; no predictive
  modelling, no forward risk score.
- Project-level only, ≥₹150 cr — the great mass of rural/state acquisitions is invisible.
- "Reason for delay" is a free-text/《categorical》 officer entry, not an inferred driver.
- No land-parcel or landowner dimension at all.

## 3. Bhoomi Rashi — MoRTH/NHAI
**What it is:** end-to-end digitised 3A/3D notification workflow for national-highway land
acquisition, integrated with PFMS for compensation disbursal.
**Weaknesses**
- **Workflow automation, not intelligence** — it accelerates notification issuance, but has no
  view on which parcels will contest, litigate, or stall.
- Scoped to NH projects under the NH Act 1956; does not cover LARR Act 2013 acquisitions.
- NHAI's own 336-day standard timeline (Apr 2025) is a *static SLA*, not a per-project forecast:
  every project gets the same clock regardless of terrain, ownership fragmentation, or history.

## 4. PM Gati Shakti National Master Plan (BISAG-N)
**What it is:** GIS layering of 1,600+ data layers for multi-modal infrastructure planning;
used for route alignment and clearance identification.
**Weaknesses**
- **Planning-stage GIS visualisation only** — no temporal model, no execution-stage risk.
- It answers "where should this go?", never "will this acquisition finish on time?".
- Land-ownership and encumbrance layers are inconsistent across states.

## 5. PRAGATI
**What it is:** PM-chaired monthly video-conference review of stuck projects.
**Weaknesses**
- **Escalation is manual and reactive**; a project reaches PRAGATI *after* it is visibly stuck,
  typically months to years late.
- Extremely low throughput — a handful of projects per session.
- No systematic method for choosing which projects to escalate.

## 6. DILRMP / Bhu-Naksha / SVAMITVA — DoLR
**What it is:** land-record digitisation, cadastral map digitisation, rural property cards.
**Weaknesses relevant to us**
- Produces the *substrate* (RoR, parcel maps) but does no acquisition-process reasoning.
- Record-of-rights quality varies sharply by state; mutation backlogs and unclear titles are
  themselves a leading delay driver — and nothing currently scores that.

## 7. Academic / commercial
Construction-delay ML literature exists (delay-risk prediction using ML/DL/hybrid models,
regression models for South Asian infrastructure delays), but it is **project-level construction
delay**, trained on schedule/cost variables — not on the statutory land-acquisition pipeline,
not deployed as a government system, and not parcel-aware.

## The white space (one line)
Every incumbent either **records the past** (LACRRIS, PAIMANA), **speeds up paperwork**
(Bhoomi Rashi), **maps space without time** (Gati Shakti), or **escalates by hand** (PRAGATI).
None produces a **forward-looking, per-project, parcel-aware, explained probability of delay
with a prescribed intervention** — which is exactly the system LADE builds.

## Sources
- LACRRIS home / dashboard / user manual — https://larr.dolr.gov.in/
- PAIMANA — https://paimana-proj.mospi.gov.in/ ; https://informatics.nic.in/files/websites/october-2025/paimana-portal.php
- PAIMANA explainer — https://organiser.org/2026/02/11/341942/bharat/what-is-paimana-and-how-is-it-monitoring-indias-rs-29-68-lakh-crore-infrastructure-projects/
- NHAI 336-day land acquisition timeline — https://foxmandal.in/News/nhai-publishes-timeline-to-streamlines-land-acquisition-activities/
- DILRMP — https://dolr.gov.in/en/programmes-schemes/dilrmp-2/
- Delay Analysis of Infrastructure Construction Projects in India — https://link.springer.com/article/10.1007/s40030-025-00899-5
- Cost and time overruns in Indian infrastructure — https://www.ijcrt.org/papers/IJCRT2508391.pdf
