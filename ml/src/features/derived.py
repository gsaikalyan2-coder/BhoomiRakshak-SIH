"""Derived scores — application features, persisted per project, never model inputs.

Three scores:
  * compensation-gap index      — refusal risk from the circle-rate benchmark gap
  * litigation-propensity score — fragmentation + title clarity + live dispute posture
  * succession risk band        — deterministic rule, reimplemented byte-for-byte from
                                  ml/src/data/generate_dataset.py::succession_risk()

The succession rule must never disagree with the seeded `succession_risk` table. Phase 2's
exit criterion asserts equality across all 362 parcels; do not "improve" the thresholds.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# --------------------------------------------------------------- compensation-gap index


def compensation_gap_index(projects: pd.DataFrame) -> pd.DataFrame:
    """0-100 refusal-risk index from the circle-rate gap and disbursal shortfall.

    `compensation_gap_pct` is how far the sanctioned amount sits below the fair value
    implied by the circle rate. A large gap that is also largely undisbursed is the worst
    case: the landowner has neither an acceptable offer nor money in hand.
    """
    gap = pd.to_numeric(projects["compensation_gap_pct"], errors="coerce").fillna(0.0)
    disbursed = pd.to_numeric(
        projects["compensation_disbursed_pct"], errors="coerce"
    ).fillna(0.0)
    appeals = pd.to_numeric(
        projects["no_compensation_appeals"], errors="coerce"
    ).fillna(0.0)

    gap_component = np.clip(gap, 0, 60) / 60.0          # 0-1, saturates at a 60% gap
    shortfall_component = (100.0 - np.clip(disbursed, 0, 100)) / 100.0
    appeal_component = np.clip(appeals, 0, 5) / 5.0

    index = 100.0 * (
        0.50 * gap_component + 0.35 * shortfall_component + 0.15 * appeal_component
    )

    band = pd.cut(
        index,
        bins=[-0.01, 33.0, 66.0, 100.01],
        labels=["Low", "Medium", "High"],
    ).astype(str)

    reason = np.where(
        gap >= 25,
        "Compensation sanctioned is "
        + gap.round(0).astype(int).astype(str)
        + "% below the circle-rate benchmark",
        np.where(
            disbursed < 50,
            "Only "
            + disbursed.round(0).astype(int).astype(str)
            + "% of the sanctioned award has actually been disbursed",
            "Compensation is close to the circle-rate benchmark and largely disbursed",
        ),
    )

    return pd.DataFrame(
        {
            "ulpin": projects["ulpin"].to_numpy(),
            "compensation_gap_index": index.round(2).to_numpy(),
            "compensation_gap_band": band,
            "compensation_gap_reason": reason,
        }
    )


# ----------------------------------------------------------- litigation-propensity score


TITLE_WEIGHT = {"Clear": 0.0, "Partial": 0.5, "Disputed": 1.0}
DISPUTE_STAGE_WEIGHT = {
    "None": 0.0,
    "Resolved": 0.15,
    "Filed": 0.55,
    "Under Hearing": 0.80,
    "Stayed by Court": 1.0,
}


def litigation_propensity_score(projects: pd.DataFrame) -> pd.DataFrame:
    """0-100 likelihood the file ends up in court, or stays there.

    Combines structural exposure (how fragmented the ownership is, how clear the title is)
    with the live posture (how many disputes exist and how far they have escalated).
    """
    frag = pd.to_numeric(
        projects["ownership_fragmentation_index"], errors="coerce"
    ).fillna(0.0)
    title = projects["title_clarity_status"].astype(str).map(TITLE_WEIGHT).fillna(0.5)
    stage = (
        projects["legal_dispute_stage"].astype(str).map(DISPUTE_STAGE_WEIGHT).fillna(0.0)
    )
    n_disputes = pd.to_numeric(projects["no_legal_disputes"], errors="coerce").fillna(0.0)
    n_owner_disputes = pd.to_numeric(
        projects["no_ownership_disputes"], errors="coerce"
    ).fillna(0.0)
    stay = (
        projects["court_stay_flag"].astype(str).str.lower().eq("true").astype(float)
        if projects["court_stay_flag"].dtype == object
        else projects["court_stay_flag"].astype(float)
    )

    frag_component = np.clip((frag - 1.0) / 2.0, 0, 1)    # index is ~1.0 upward
    dispute_component = np.clip(n_disputes / 5.0, 0, 1)
    owner_component = np.clip(n_owner_disputes / 5.0, 0, 1)

    score = 100.0 * np.clip(
        0.22 * frag_component
        + 0.20 * title
        + 0.26 * stage
        + 0.16 * dispute_component
        + 0.10 * owner_component
        + 0.06 * stay,
        0,
        1,
    )

    band = pd.cut(
        score, bins=[-0.01, 33.0, 66.0, 100.01], labels=["Low", "Medium", "High"]
    ).astype(str)

    reason = np.where(
        stay > 0,
        "A court stay is in force — the acquisition cannot proceed until it is vacated",
        np.where(
            stage >= 0.55,
            "Dispute at "
            + projects["legal_dispute_stage"].astype(str)
            + " with "
            + n_disputes.astype(int).astype(str)
            + " matter(s) on file",
            np.where(
                title >= 0.5,
                "Title is "
                + projects["title_clarity_status"].astype(str).str.lower()
                + " over fragmented holdings — objection risk at award",
                "Clear title, no live litigation on record",
            ),
        ),
    )

    return pd.DataFrame(
        {
            "ulpin": projects["ulpin"].to_numpy(),
            "litigation_propensity_score": np.round(score, 2),
            "litigation_propensity_band": band,
            "litigation_propensity_reason": reason,
        }
    )


# ------------------------------------------------------------------------ succession risk


def succession_risk(claims: pd.DataFrame) -> pd.DataFrame:
    """Deterministic RULE, not a model. Identical to generate_dataset.py::succession_risk().

    High   — any contested claim, OR claimed shares total > 105% of the parcel
    Medium — any undocumented claim, OR more than 2 heirs on one parcel
    Low    — every heirship claim documented
    """
    cols = [
        "ulpin",
        "heir_claim_count",
        "undocumented_claims",
        "contested_claims",
        "share_total_pct",
        "succession_risk_band",
        "succession_reason",
    ]
    if claims.empty:
        return pd.DataFrame(columns=cols)

    g = claims.groupby("ulpin")
    out = pd.DataFrame(
        {
            "heir_claim_count": g.size(),
            "undocumented_claims": g.proof_status.apply(
                lambda s: (s == "Undocumented").sum()
            ),
            "contested_claims": g.proof_status.apply(lambda s: (s == "Contested").sum()),
            "share_total_pct": g.claimed_share_pct.sum().round(1),
        }
    ).reset_index()

    def band(r):
        if r.contested_claims > 0 or r.share_total_pct > 105:
            return "High", (
                "Competing heirship claims over the same parcel"
                if r.contested_claims
                else f"Claimed shares total {r.share_total_pct}% — exceeds the parcel"
            )
        if r.undocumented_claims > 0:
            return "Medium", (
                f"{r.undocumented_claims} heir claim(s) without documentary proof "
                "— mutation not established"
            )
        if r.heir_claim_count > 2:
            return "Medium", f"{r.heir_claim_count} heirs on one parcel — consent risk at award"
        return "Low", "All heirship claims documented"

    b = out.apply(band, axis=1, result_type="expand")
    out["succession_risk_band"], out["succession_reason"] = b[0], b[1]
    return out[cols]


# ------------------------------------------------------------------------------ combine


def compute_all(projects: pd.DataFrame, claims: pd.DataFrame) -> pd.DataFrame:
    """One row per project carrying all three derived scores. Persisted by the registry."""
    gap = compensation_gap_index(projects)
    lit = litigation_propensity_score(projects)
    suc = succession_risk(claims)

    out = gap.merge(lit, on="ulpin", how="outer").merge(suc, on="ulpin", how="left")
    out["succession_risk_band"] = out["succession_risk_band"].fillna("Not Applicable")
    out["succession_reason"] = out["succession_reason"].fillna(
        "No heirship claim on file for this parcel"
    )
    for c in ("heir_claim_count", "undocumented_claims", "contested_claims"):
        out[c] = out[c].fillna(0).astype(int)
    out["share_total_pct"] = out["share_total_pct"].fillna(0.0)
    return out
