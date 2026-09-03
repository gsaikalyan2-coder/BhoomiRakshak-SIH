"""Hyperparameters for the two models. Kept apart from the training loop so a retune is a
one-file change and the training script stays readable.

Both are deliberately small. 600 training rows is not a lot; deep trees memorise it and the
CV numbers stop meaning anything.
"""

from __future__ import annotations

from xgboost import XGBClassifier

RANDOM_STATE = 20260823

MODEL_A_PARAMS = dict(
    n_estimators=400,
    max_depth=4,
    learning_rate=0.05,
    subsample=0.85,
    colsample_bytree=0.75,
    min_child_weight=3,
    reg_lambda=2.0,
    objective="binary:logistic",
    eval_metric="auc",
    tree_method="hist",
    random_state=RANDOM_STATE,
    n_jobs=4,
)

MODEL_B_PARAMS = dict(
    n_estimators=350,
    max_depth=4,
    learning_rate=0.06,
    subsample=0.85,
    colsample_bytree=0.75,
    min_child_weight=2,
    reg_lambda=2.0,
    objective="multi:softprob",
    eval_metric="mlogloss",
    tree_method="hist",
    random_state=RANDOM_STATE,
    n_jobs=4,
)


def make_model_a() -> XGBClassifier:
    """Model A — binary `is_delayed`, trained on the 600 closed projects only."""
    return XGBClassifier(**MODEL_A_PARAMS)


def make_model_b(num_class: int) -> XGBClassifier:
    """Model B — 5-class `delay_stage`, conditional on delay."""
    return XGBClassifier(num_class=num_class, **MODEL_B_PARAMS)
