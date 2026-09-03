"""ml.src.explainability — SHAP TreeExplainer plus the officer-language reason-code map."""

from .explainer import Factor, ProjectExplanation, RiskExplainer, top_factors
from .reason_codes import FACTOR_GROUPS, TEMPLATES, describe, group_of

__all__ = [
    "FACTOR_GROUPS",
    "Factor",
    "ProjectExplanation",
    "RiskExplainer",
    "TEMPLATES",
    "describe",
    "group_of",
    "top_factors",
]
