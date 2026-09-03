"""SHAP explanations in officer language.

`shap.TreeExplainer` on the raw XGBoost booster (not the calibrator — isotonic regression
is not a tree model and TreeExplainer cannot walk it). Calibration is monotone, so the sign
and the ranking of every contribution are preserved; only the absolute probability shifts.

The public surface is one function:

    explain_project(row) -> ProjectExplanation

with `.top_factors(n)` returning the top-N factors with a signed contribution percentage
and a display label ready for `risk_reasons.display_label`.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd
import shap

from ..features.build import FeatureSpec, build_feature_matrix
from ..models import registry as reg
from . import reason_codes


@dataclass(frozen=True)
class Factor:
    feature: str
    value: float
    shap_value: float
    contribution_pct: float          # signed, % of total |SHAP| mass for this row
    direction: str                   # "increases risk" | "reduces risk"
    group: str
    display_label: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ProjectExplanation:
    ulpin: str
    risk_probability: float
    base_value: float
    factors: list[Factor]

    def top_factors(self, n: int = 3) -> list[Factor]:
        return self.factors[:n]

    def to_dict(self, n: int | None = None) -> dict:
        f = self.factors if n is None else self.factors[:n]
        return {
            "ulpin": self.ulpin,
            "risk_probability": round(self.risk_probability, 4),
            "base_value": round(self.base_value, 4),
            "factors": [x.to_dict() for x in f],
        }


class RiskExplainer:
    """Loads a registry version and explains single projects or batches."""

    def __init__(
        self,
        model,
        spec: FeatureSpec,
        calibrator=None,
        stage_model=None,
        stage_classes: list[str] | None = None,
    ):
        self.model = model
        self.spec = spec
        self.calibrator = calibrator
        self.stage_model = stage_model
        self.stage_classes = stage_classes or []
        self._explainer = shap.TreeExplainer(model)

    # ------------------------------------------------------------------ constructors
    @classmethod
    def from_registry(
        cls, version: str | None = None, registry_path: str | pathlib.Path | None = None
    ) -> "RiskExplainer":
        import joblib
        from xgboost import XGBClassifier

        version = version or reg.active_version(registry_path)
        d = reg.version_dir(version, registry_path)

        a = XGBClassifier()
        a.load_model(d / "model_a_is_delayed.json")

        b = None
        meta = reg.read_json(d / "metadata.json")
        if (d / "model_b_delay_stage.json").exists():
            b = XGBClassifier()
            b.load_model(d / "model_b_delay_stage.json")

        cal_path = d / "model_a_calibrator.joblib"
        cal = joblib.load(cal_path) if cal_path.exists() else None

        spec = FeatureSpec.from_dict(reg.read_json(d / "feature_spec.json"))
        return cls(a, spec, cal, b, meta.get("delay_stage_classes", []))

    # ---------------------------------------------------------------------- scoring
    def calibrated_probability(self, X: pd.DataFrame) -> np.ndarray:
        raw = self.model.predict_proba(X)[:, 1]
        if self.calibrator is None:
            return raw
        return np.clip(self.calibrator.predict(raw), 0.0, 1.0)

    def predict_stage(self, X: pd.DataFrame) -> list[dict]:
        """Model B — conditional stage distribution. Meaningful only where risk is high."""
        if self.stage_model is None:
            return [{} for _ in range(len(X))]
        proba = self.stage_model.predict_proba(X)
        out = []
        for row in proba:
            order = np.argsort(row)[::-1]
            out.append(
                {
                    "predicted_stage": self.stage_classes[order[0]],
                    "confidence": round(float(row[order[0]]), 4),
                    "distribution": {
                        self.stage_classes[i]: round(float(row[i]), 4)
                        for i in order
                    },
                }
            )
        return out

    # ------------------------------------------------------------------ explanation
    def explain_frame(self, df: pd.DataFrame) -> list[ProjectExplanation]:
        X, _ = build_feature_matrix(df, self.spec)
        sv = self._explainer.shap_values(X)
        if isinstance(sv, list):                       # older shap multiclass shape
            sv = sv[1]
        base = self._explainer.expected_value
        base = float(np.ravel(base)[0])
        probs = self.calibrated_probability(X)
        ulpins = (
            df["ulpin"].astype(str).tolist()
            if "ulpin" in df.columns
            else [f"row-{i}" for i in range(len(df))]
        )

        out = []
        for i in range(len(X)):
            contrib = sv[i]
            total = float(np.abs(contrib).sum()) or 1.0
            order = np.argsort(np.abs(contrib))[::-1]
            factors = []
            for j in order:
                name = X.columns[j]
                val = float(X.iloc[i, j])
                s = float(contrib[j])
                if abs(s) < 1e-9:
                    continue
                factors.append(
                    Factor(
                        feature=name,
                        value=round(val, 4),
                        shap_value=round(s, 5),
                        contribution_pct=round(100.0 * s / total, 2),
                        direction="increases risk" if s > 0 else "reduces risk",
                        group=reason_codes.group_of(name),
                        display_label=reason_codes.describe(name, val),
                    )
                )
            out.append(
                ProjectExplanation(
                    ulpin=ulpins[i],
                    risk_probability=float(probs[i]),
                    base_value=base,
                    factors=factors,
                )
            )
        return out

    def explain_project(self, row: pd.Series | dict) -> ProjectExplanation:
        """`project_row -> top-N factors with signed contribution %`. The Phase 2 deliverable."""
        if isinstance(row, dict):
            df = pd.DataFrame([row])
        else:
            df = row.to_frame().T
        return self.explain_frame(df)[0]


def top_factors(row: pd.Series | dict, n: int = 3, version: str | None = None) -> list[dict]:
    """Convenience one-shot: load the active model and explain one project row."""
    return [f.to_dict() for f in RiskExplainer.from_registry(version).explain_project(row).top_factors(n)]
