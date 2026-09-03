"""ml.src.serving — reserved for Phase 3.

Serving loads models through ml.src.explainability.RiskExplainer.from_registry() and builds
features through ml.src.features.build_feature_matrix(df, explainer.spec). Nothing in the
backend rebuilds features; this package exists so that boundary has a home if serving-only
helpers are ever needed.
"""
