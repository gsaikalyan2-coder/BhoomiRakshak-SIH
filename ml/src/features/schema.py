"""Feature schema — the single source of truth for BhoomiRakshak's feature matrix.

Nothing in this module may be duplicated in the backend. Training (Phase 2) and serving
(Phase 3) both import from here; if the two ever disagree, the model is silently wrong.

Two rules are enforced, both taken from docs/research/dataset-audit.md §"Two rules":

1. The mandatory drop-list. `latent_risk_audit` and `top_driver_audit` are the dataset
   generator's own ground truth and leak the label outright.
2. Explicit ordinal encodings. `pandas.Categorical.cat.codes` orders alphabetically, which
   scrambles every ordinal below and flattens `title_clarity_status` and
   `legal_dispute_stage` to zero importance.

One further trap, recorded as Phase 1 finding 3: `legal_dispute_stage` carries the literal
string "None", meaning "no dispute on file" — ordinal level 0, NOT a missing value.
`pandas.read_csv` converts it to NaN by default and destroys the level. `load_projects()`
below reads that column through a `str` converter, which bypasses NA coercion entirely.
"""

from __future__ import annotations

# --------------------------------------------------------------------------- drop-list
#: Columns that must never reach either model. Asserted by ml/tests/test_features.py.
DROP_LIST: tuple[str, ...] = (
    "ulpin",
    "project_name",
    "latent_risk_audit",
    "top_driver_audit",
    "is_delayed",
    "delay_stage",
    "historical_delay_days",
    "actual_completion_date",
    "assigned_field_officer_id",
    "notification_date",
    "expected_completion_date",
    "is_closed_project",
    "planned_duration_days",
    "taluk",
    "village",
)

# --------------------------------------------------------------------- ordinal encodings
TITLE_CLARITY_ORDER: dict[str, int] = {
    "Clear": 0,
    "Partial": 1,
    "Disputed": 2,
}

#: "None" is a VALUE (no dispute on file), not a null. See Phase 1 finding 3.
LEGAL_DISPUTE_STAGE_ORDER: dict[str, int] = {
    "None": 0,
    "Resolved": 1,
    "Filed": 2,
    "Under Hearing": 3,
    "Stayed by Court": 4,
}

#: Clearance ladder. "Not Required" and "Obtained" are both level 0 — neither blocks the file.
CLEARANCE_ORDER: dict[str, int] = {
    "Not Required": 0,
    "Obtained": 0,
    "Applied": 1,
    "Pending": 2,
}

#: LARR statutory ladder in *exposure* order: the further from possession, the more risk
#: exposure remains. Possession Taken 0 … SIA Completed 5.
APPROVAL_STAGE_ORDER: dict[str, int] = {
    "Possession Taken": 0,
    "R&R Implementation": 1,
    "Compensation Disbursement": 2,
    "Award Declared": 3,
    "Section 11 Notification Issued": 4,
    "SIA Completed": 5,
}

ORDINAL_ENCODINGS: dict[str, dict[str, int]] = {
    "title_clarity_status": TITLE_CLARITY_ORDER,
    "legal_dispute_stage": LEGAL_DISPUTE_STAGE_ORDER,
    "environmental_clearance_status": CLEARANCE_ORDER,
    "forest_clearance_status": CLEARANCE_ORDER,
    "approval_stage": APPROVAL_STAGE_ORDER,
}

#: Columns read as raw strings so pandas cannot coerce a meaningful value to NaN.
STRING_CONVERTER_COLUMNS: tuple[str, ...] = tuple(ORDINAL_ENCODINGS)

# --------------------------------------------------------------------------- one-hot
ONE_HOT_COLUMNS: tuple[str, ...] = (
    "project_type",
    "implementing_agency",
    "state",
    "district",
)

# --------------------------------------------------------------------------- numeric
NUMERIC_COLUMNS: tuple[str, ...] = (
    "latitude",
    "longitude",
    "land_area_acres",
    "no_affected_families",
    "no_landowners",
    "ownership_fragmentation_index",
    "no_ownership_disputes",
    "circle_rate_per_acre_lakhs",
    "compensation_fair_value_lakhs",
    "compensation_amount_sanctioned_lakhs",
    "compensation_amount_disbursed_lakhs",
    "compensation_disbursed_pct",
    "compensation_gap_pct",
    "no_compensation_appeals",
    "no_legal_disputes",
    "days_since_dispute_filed",
    "rehab_progress_pct",
    "no_families_resettled",
    "days_in_current_stage",
    "no_pending_clearances",
)

BOOLEAN_COLUMNS: tuple[str, ...] = (
    "ownership_dispute_flag",
    "compensation_dispute_flag",
    "court_stay_flag",
    "rehab_plan_approved_flag",
    "resettlement_site_ready_flag",
)

# --------------------------------------------------------------------------- targets
BINARY_TARGET = "is_delayed"
STAGE_TARGET = "delay_stage"

#: `delay_stage` for a project that did not slip. Excluded from Model B's training set —
#: Model B is conditional on delay.
STAGE_NOT_APPLICABLE = "Not Applicable"

#: The five classes Model B predicts, in a fixed order so class indices are stable across
#: retrains and across the training/serving boundary.
DELAY_STAGE_CLASSES: tuple[str, ...] = (
    "Compensation Disbursal",
    "Legal Dispute",
    "Rehabilitation (R&R)",
    "Ownership / Title",
    "Administrative Approval",
)

# ------------------------------------------------------------------- derived scores
#: Derived scores are APPLICATION features, persisted per project and rendered in the UI.
#: They are deliberately NOT model inputs:
#:   * succession risk is a deterministic rule, and the PDF requires it never be trained on;
#:   * the compensation-gap index and litigation-propensity score are collinear transforms
#:     of columns the model already sees, so feeding them back would only cannibalise the
#:     SHAP importance of the raw drivers an officer needs to see named.
DERIVED_SCORE_COLUMNS: tuple[str, ...] = (
    "compensation_gap_index",
    "litigation_propensity_score",
    "succession_risk_band",
)
