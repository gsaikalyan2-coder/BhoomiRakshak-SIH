"""Feature name → officer language.

SHAP gives us `compensation_gap_pct = 34.2, shap = +0.41`. An officer needs
*"Compensation offered is 34% below the circle-rate benchmark"*. This module is that
translation, and its output lands in `risk_reasons.display_label` in Phase 3.

Every entry states a fact about the file, in the register a District Collector's note uses.
Never a feature name, never a probability, never a recommendation — recommendations are
Phase 6 and are keyed on these same factor codes.
"""

from __future__ import annotations

from typing import Callable

from ..features.schema import (
    APPROVAL_STAGE_ORDER,
    CLEARANCE_ORDER,
    LEGAL_DISPUTE_STAGE_ORDER,
    TITLE_CLARITY_ORDER,
)


def _inv(mapping: dict[str, int]) -> dict[int, str]:
    out: dict[int, str] = {}
    for k, v in mapping.items():
        out.setdefault(v, k)
    return out


_TITLE = _inv(TITLE_CLARITY_ORDER)
_DISPUTE = _inv(LEGAL_DISPUTE_STAGE_ORDER)
_CLEAR = {0: "obtained or not required", 1: "applied for", 2: "still pending"}
_STAGE = _inv(APPROVAL_STAGE_ORDER)


def _i(v) -> int:
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return 0


def _f(v, nd: int = 1) -> str:
    try:
        return f"{float(v):.{nd}f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return str(v)


#: feature name → callable(raw_value) -> officer sentence.
TEMPLATES: dict[str, Callable] = {
    "compensation_gap_pct": lambda v: (
        f"Compensation sanctioned is {_i(v)}% below the circle-rate benchmark"
    ),
    "compensation_disbursed_pct": lambda v: (
        f"Only {_i(v)}% of the sanctioned award has actually reached landowners"
    ),
    "compensation_amount_disbursed_lakhs": lambda v: (
        f"₹{_f(v)} lakh disbursed against the award so far"
    ),
    "compensation_amount_sanctioned_lakhs": lambda v: (
        f"Award sanctioned at ₹{_f(v)} lakh"
    ),
    "compensation_fair_value_lakhs": lambda v: (
        f"Circle-rate fair value of the parcel works out to ₹{_f(v)} lakh"
    ),
    "circle_rate_per_acre_lakhs": lambda v: (
        f"Circle rate for this land is ₹{_f(v)} lakh per acre"
    ),
    "no_compensation_appeals": lambda v: (
        f"{_i(v)} compensation appeal(s) pending against the award"
        if _i(v)
        else "No compensation appeal on record"
    ),
    "compensation_dispute_flag": lambda v: (
        "Compensation is formally disputed by affected landowners"
        if _i(v)
        else "Compensation is not under dispute"
    ),
    "no_legal_disputes": lambda v: (
        f"{_i(v)} legal matter(s) filed against this acquisition"
        if _i(v)
        else "No litigation on record against this acquisition"
    ),
    "legal_dispute_stage": lambda v: (
        "No dispute on file"
        if _i(v) == 0
        else f"Litigation has reached the '{_DISPUTE.get(_i(v), 'unknown')}' stage"
    ),
    "court_stay_flag": lambda v: (
        "A court stay is in force — acquisition cannot proceed until it is vacated"
        if _i(v)
        else "No court stay in force"
    ),
    "days_since_dispute_filed": lambda v: (
        f"The dispute has been live for {_i(v)} days"
        if _i(v)
        else "No dispute clock running"
    ),
    "title_clarity_status": lambda v: (
        f"Record-of-rights title is {_TITLE.get(_i(v), 'unknown').lower()}"
    ),
    "ownership_fragmentation_index": lambda v: (
        f"Ownership is fragmented at an index of {_f(v, 2)} — many small holdings per parcel"
    ),
    "no_ownership_disputes": lambda v: (
        f"{_i(v)} ownership dispute(s) recorded over the parcel"
        if _i(v)
        else "No ownership dispute recorded"
    ),
    "ownership_dispute_flag": lambda v: (
        "Ownership of the parcel is contested"
        if _i(v)
        else "Ownership of the parcel is uncontested"
    ),
    "no_landowners": lambda v: f"{_i(v)} recorded landowners must each consent",
    "no_affected_families": lambda v: f"{_i(v)} affected families in the acquisition",
    "land_area_acres": lambda v: f"Acquisition covers {_f(v)} acres",
    "rehab_progress_pct": lambda v: (
        f"Rehabilitation and resettlement is {_i(v)}% complete"
    ),
    "rehab_plan_approved_flag": lambda v: (
        "R&R plan is approved"
        if _i(v)
        else "R&R plan has not yet been approved"
    ),
    "resettlement_site_ready_flag": lambda v: (
        "Resettlement site is ready for occupation"
        if _i(v)
        else "Resettlement site is not yet ready"
    ),
    "no_families_resettled": lambda v: f"{_i(v)} families resettled to date",
    "approval_stage": lambda v: (
        f"File is at the '{_STAGE.get(_i(v), 'unknown')}' stage of the LARR process"
    ),
    "days_in_current_stage": lambda v: (
        f"The file has sat at its current stage for {_i(v)} days"
    ),
    "no_pending_clearances": lambda v: (
        f"{_i(v)} statutory clearance(s) still pending"
        if _i(v)
        else "No statutory clearance outstanding"
    ),
    "environmental_clearance_status": lambda v: (
        f"Environmental clearance is {_CLEAR.get(_i(v), 'unknown')}"
    ),
    "forest_clearance_status": lambda v: (
        f"Forest clearance is {_CLEAR.get(_i(v), 'unknown')}"
    ),
    "latitude": lambda v: "Project location",
    "longitude": lambda v: "Project location",
}

#: Officer-facing grouping, so the Project Detail screen can cluster the SHAP bars.
FACTOR_GROUPS: dict[str, str] = {
    **{
        c: "Compensation"
        for c in (
            "compensation_gap_pct",
            "compensation_disbursed_pct",
            "compensation_amount_disbursed_lakhs",
            "compensation_amount_sanctioned_lakhs",
            "compensation_fair_value_lakhs",
            "circle_rate_per_acre_lakhs",
            "no_compensation_appeals",
            "compensation_dispute_flag",
        )
    },
    **{
        c: "Legal"
        for c in (
            "no_legal_disputes",
            "legal_dispute_stage",
            "court_stay_flag",
            "days_since_dispute_filed",
        )
    },
    **{
        c: "Ownership / Title"
        for c in (
            "title_clarity_status",
            "ownership_fragmentation_index",
            "no_ownership_disputes",
            "ownership_dispute_flag",
            "no_landowners",
        )
    },
    **{
        c: "Rehabilitation (R&R)"
        for c in (
            "rehab_progress_pct",
            "rehab_plan_approved_flag",
            "resettlement_site_ready_flag",
            "no_families_resettled",
            "no_affected_families",
        )
    },
    **{
        c: "Administrative"
        for c in (
            "approval_stage",
            "days_in_current_stage",
            "no_pending_clearances",
            "environmental_clearance_status",
            "forest_clearance_status",
        )
    },
}

_ONE_HOT_PREFIXES = {
    "project_type": "Project type",
    "implementing_agency": "Implementing agency",
    "state": "State",
    "district": "District",
}


def describe(feature: str, value) -> str:
    """One officer-readable sentence for a feature and the value this project carries."""
    if feature in TEMPLATES:
        return TEMPLATES[feature](value)
    for prefix, label in _ONE_HOT_PREFIXES.items():
        if feature.startswith(prefix + "_"):
            level = feature[len(prefix) + 1 :].replace("_", " ")
            present = _i(value) == 1
            return (
                f"{label} is {level}"
                if present
                else f"{label} is not {level}"
            )
    return feature.replace("_", " ").capitalize()


def group_of(feature: str) -> str:
    if feature in FACTOR_GROUPS:
        return FACTOR_GROUPS[feature]
    for prefix in _ONE_HOT_PREFIXES:
        if feature.startswith(prefix + "_"):
            return "Context"
    return "Context"
