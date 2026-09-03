# Gap Coverage Matrix — which hole in which system BhoomiRakshak closes
Rev 1, 2026-08-23. Pair this with competitive-landscape.md. This is the table to put on a slide.

| # | Hole in the existing landscape | Which system has it | How BhoomiRakshak closes it | Build item |
|---|---|---|---|---|
| 1 | Records that a delay happened, never that one is coming | LACRRIS, PAIMANA | `is_delayed` probability per project, forward-looking | #2 |
| 2 | Says a project is at risk but not **where** it will break | all of them | `delay_stage` multi-class: names the stage that will stall | #3 |
| 3 | Delay "reason" is a free-text officer entry, not inferred | PAIMANA, LACRRIS | SHAP per-prediction contributions, top-3 drivers with % | #5 |
| 4 | Flags a problem and stops | every govt dashboard | Rule-based + Flan-T5 corrective action paired to each driver | #11, #12 |
| 5 | Passive reporting — cannot test an intervention | all of them | What-if simulator: move disbursement %, watch risk recompute live | #13 |
| 6 | Compensation tracked as % disbursed only, never **adequacy** | LACRRIS, Bhoomi Rashi | Compensation-gap index: offered vs circle-rate benchmark → refusal risk | #4 |
| 7 | Title/ownership quality never scored as delay risk | DILRMP digitises records but scores nothing | Litigation-propensity from ownership fragmentation + title clarity | #4 |
| 8 | Time a file sits on a desk is invisible | none track it | SLA / stuck-file clock: "at legal review 47 days" | #14 |
| 9 | Static, uniform SLAs regardless of project character | NHAI 336-day timeline | Model-derived per-project expectation replaces the flat clock | #2, #14 |
| 10 | Escalation is manual and months late | PRAGATI | Automatic threshold-breach alert by real email to the named officer | #15 |
| 11 | GIS exists for planning, not for execution risk | PM Gati Shakti | Leaflet risk-coloured pins + district risk heatmap on live scores | #10, #17 |
| 12 | No officer can ask the system a question | all of them | NL query: "which projects in my district slip in 30 days?" | #19 |
| 13 | Collector reads tables, not conclusions | all of them | Weekly auto-generated district brief in plain language | #18 |
| 14 | Officer sees the same national view as the secretary | LACRRIS (public reports only) | JWT role + district scoping: field officer sees only their jurisdiction | #1 |
| 15 | No record of who saw a risk and what they did about it | all of them | Admin annotation + full audit log of every score served and action taken | #16 |
| 16 | ≥₹150 cr threshold hides the bulk of rural acquisition | PAIMANA | No value floor — every LARR case is scored | #0 |

## The two honest limits — say these before a judge finds them
1. **Training data is synthetic.** No public land-acquisition delay-risk dataset exists in India —
   which is itself the novelty argument. The generator is modelled on real LARR Act 2013 parameters
   and DILRMP/ULPIN structure, with correlations deliberately injected so SHAP finds real drivers.
2. **Rows 6 and 7 need fields LACRRIS does not capture.** Circle-rate gap and ownership
   fragmentation are not in any existing government schema. That is an argument *for* the system —
   a deployment recommendation, not a defect — and should be stated as one.
