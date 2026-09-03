"""SHAP layer tests — that an explanation is well-formed, signed, and in officer language."""

from __future__ import annotations

import pathlib

import pandas as pd
import pytest

from ml.src.explainability import RiskExplainer, describe, group_of
from ml.src.features import load_projects, split_closed_ongoing
from ml.src.models import registry as reg

DATA = pathlib.Path(__file__).resolve().parents[1] / "data"


@pytest.fixture(scope="module")
def explainer() -> RiskExplainer:
    try:
        return RiskExplainer.from_registry()
    except FileNotFoundError:
        pytest.skip("no trained model in the registry — run ml.src.training.train first")


@pytest.fixture(scope="module")
def ongoing() -> pd.DataFrame:
    _, ongoing = split_closed_ongoing(load_projects(DATA / "projects.csv"))
    return ongoing.reset_index(drop=True)


def test_explains_a_single_project_row(explainer, ongoing):
    exp = explainer.explain_project(ongoing.iloc[0])
    assert exp.ulpin == ongoing.iloc[0].ulpin
    assert 0.0 <= exp.risk_probability <= 1.0
    top = exp.top_factors(3)
    assert len(top) == 3
    for f in top:
        assert f.direction in ("increases risk", "reduces risk")
        assert f.display_label and not f.display_label.startswith(f.feature.split("_")[0] + "_")
        assert -100.0 <= f.contribution_pct <= 100.0


def test_factors_are_ordered_by_absolute_contribution(explainer, ongoing):
    exp = explainer.explain_project(ongoing.iloc[5])
    pcts = [abs(f.contribution_pct) for f in exp.factors]
    assert pcts == sorted(pcts, reverse=True)


def test_contributions_sum_to_one_hundred_percent(explainer, ongoing):
    exp = explainer.explain_project(ongoing.iloc[9])
    assert abs(sum(abs(f.contribution_pct) for f in exp.factors) - 100.0) < 1.0


def test_batch_and_single_agree(explainer, ongoing):
    batch = explainer.explain_frame(ongoing.head(4))
    single = explainer.explain_project(ongoing.iloc[2])
    assert batch[2].ulpin == single.ulpin
    assert abs(batch[2].risk_probability - single.risk_probability) < 1e-9


def test_calibrated_probability_stays_in_range(explainer, ongoing):
    exps = explainer.explain_frame(ongoing.head(50))
    assert all(0.0 <= e.risk_probability <= 1.0 for e in exps)


def test_stage_prediction_returns_a_named_class(explainer, ongoing):
    from ml.src.features.build import build_feature_matrix

    X, _ = build_feature_matrix(ongoing.head(3), explainer.spec)
    out = explainer.predict_stage(X)
    assert len(out) == 3
    for o in out:
        assert o["predicted_stage"] in explainer.stage_classes
        assert 0.0 <= o["confidence"] <= 1.0


def test_reason_codes_speak_officer_language():
    assert "circle-rate benchmark" in describe("compensation_gap_pct", 34.2)
    assert "34%" in describe("compensation_gap_pct", 34.2)
    assert describe("legal_dispute_stage", 0) == "No dispute on file"
    assert "Stayed by Court" in describe("legal_dispute_stage", 4)
    assert "disputed" in describe("title_clarity_status", 2).lower()
    assert group_of("compensation_gap_pct") == "Compensation"
    assert group_of("no_legal_disputes") == "Legal"


def test_reason_code_exists_for_every_feature_in_the_spec(explainer):
    """No SHAP bar may render as a raw column name on the Project Detail screen."""
    for col in explainer.spec.columns:
        label = describe(col, 0)
        assert label and label != col


def test_registry_metadata_names_the_active_version():
    meta = reg.read_json(reg.version_dir(reg.active_version()) / "metadata.json")
    assert meta["model_version"] == reg.active_version()
    assert meta["n_closed_training"] == 600
    assert len(meta["delay_stage_classes"]) == 5
