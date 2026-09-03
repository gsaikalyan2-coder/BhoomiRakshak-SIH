"""Feature-contract tests. These are the guard rails, not decoration.

The drop-list test is a Phase 2 exit criterion: if `latent_risk_audit` or `top_driver_audit`
ever reaches the matrix, both models score near-perfect for a circular reason and SHAP
reports the generator's own ground truth as the cause of delay.
"""

from __future__ import annotations

import pathlib

import pandas as pd
import pytest

from ml.src.features import (
    DROP_LIST,
    LEGAL_DISPUTE_STAGE_ORDER,
    ORDINAL_ENCODINGS,
    FeatureContractError,
    build_feature_matrix,
    load_projects,
    split_closed_ongoing,
    succession_risk,
)

DATA = pathlib.Path(__file__).resolve().parents[1] / "data"


@pytest.fixture(scope="module")
def projects() -> pd.DataFrame:
    return load_projects(DATA / "projects.csv")


# ------------------------------------------------------------------ the drop-list test
def test_no_drop_list_column_reaches_the_feature_matrix(projects):
    X, spec = build_feature_matrix(projects)
    leaked = [c for c in DROP_LIST if c in X.columns]
    assert leaked == [], f"drop-list column(s) leaked into the feature matrix: {leaked}"
    assert leaked == [c for c in DROP_LIST if c in spec.columns]


def test_no_drop_list_column_survives_one_hot_expansion(projects):
    """`taluk` and `village` are on the drop-list; no one-hot column may carry them."""
    X, _ = build_feature_matrix(projects)
    for banned in ("latent_risk_audit", "top_driver_audit", "taluk", "village", "ulpin"):
        offenders = [c for c in X.columns if c == banned or c.startswith(banned + "_")]
        assert offenders == [], f"{banned} reached the matrix as {offenders}"


def test_build_feature_matrix_rejects_a_matrix_with_a_dropped_column():
    with pytest.raises(FeatureContractError):
        from ml.src.features.build import assert_no_drop_list_columns

        assert_no_drop_list_columns(pd.DataFrame({"is_delayed": [1]}), stage="matrix")


# --------------------------------------------------------- the "None" ordinal test
def test_legal_dispute_stage_none_is_a_value_not_a_null(projects):
    """Phase 1 finding 3. `pandas.read_csv` turns "None" into NaN and kills the level."""
    assert projects["legal_dispute_stage"].isna().sum() == 0
    assert (projects["legal_dispute_stage"] == "None").sum() > 0
    X, _ = build_feature_matrix(projects)
    assert X["legal_dispute_stage"].min() == 0
    assert X["legal_dispute_stage"].max() == max(LEGAL_DISPUTE_STAGE_ORDER.values())


def test_naive_read_csv_would_have_broken_it():
    """Documents the bug so nobody 'simplifies' load_projects() back into it."""
    naive = pd.read_csv(DATA / "projects.csv")
    assert naive["legal_dispute_stage"].isna().sum() > 0


def test_every_ordinal_is_encoded_in_the_stated_order(projects):
    X, _ = build_feature_matrix(projects)
    for col, mapping in ORDINAL_ENCODINGS.items():
        assert col in X.columns
        pairs = pd.DataFrame(
            {"raw": projects[col].astype(str), "enc": X[col].to_numpy()}
        ).drop_duplicates()
        for _, r in pairs.iterrows():
            assert mapping[r.raw] == r.enc, f"{col}: {r.raw} encoded as {r.enc}"


def test_ordinals_are_not_constant(projects):
    """A collapsed ordinal shows up here before it shows up as zero importance."""
    X, _ = build_feature_matrix(projects)
    for col in ORDINAL_ENCODINGS:
        assert X[col].nunique() > 1, f"{col} collapsed to a single level"


def test_unknown_ordinal_level_raises_rather_than_becoming_nan(projects):
    bad = projects.head(5).copy()
    bad.loc[bad.index[0], "title_clarity_status"] = "Somewhat Clear"
    with pytest.raises(FeatureContractError):
        build_feature_matrix(bad)


# ------------------------------------------------------------------- shape and spec
def test_training_split_is_600_closed_300_ongoing(projects):
    closed, ongoing = split_closed_ongoing(projects)
    assert len(closed) == 600
    assert len(ongoing) == 300
    assert closed["is_delayed"].notna().all()
    assert ongoing["is_delayed"].isna().all()


def test_spec_replays_identically_on_a_single_row(projects):
    """Serving passes one project. The matrix must match training column-for-column."""
    X, spec = build_feature_matrix(projects)
    one, _ = build_feature_matrix(projects.head(1), spec)
    assert list(one.columns) == list(X.columns)
    assert (one.iloc[0].to_numpy() == X.iloc[0].to_numpy()).all()


def test_matrix_has_no_nulls(projects):
    X, _ = build_feature_matrix(projects)
    assert not X.isna().any().any()


# ------------------------------------------------------------------- succession rule
def test_succession_band_matches_the_seeded_table():
    """The rule must never disagree with the seeded succession_risk table — all 362 parcels."""
    claims = pd.read_csv(DATA / "succession_claims.csv")
    seeded = pd.read_csv(DATA / "succession_risk.csv")
    computed = succession_risk(claims)
    merged = seeded.merge(computed, on="ulpin", suffixes=("_seeded", "_computed"))
    assert len(merged) == len(seeded) == 362
    assert (
        merged["succession_risk_band_seeded"] == merged["succession_risk_band_computed"]
    ).all()
    assert (
        merged["succession_reason_seeded"] == merged["succession_reason_computed"]
    ).all()
