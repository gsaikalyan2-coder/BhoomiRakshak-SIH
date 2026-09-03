"""Feature matrix construction. Imported by training (Phase 2) and serving (Phase 3).

The backend must never rebuild features itself — it calls `build_feature_matrix()` with a
row (or rows) fetched from Postgres and gets back a frame whose columns are, in order,
exactly the columns the active model was trained on.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd

from .schema import (
    BOOLEAN_COLUMNS,
    DROP_LIST,
    NUMERIC_COLUMNS,
    ONE_HOT_COLUMNS,
    ORDINAL_ENCODINGS,
    STRING_CONVERTER_COLUMNS,
)


class FeatureContractError(RuntimeError):
    """Raised when a frame violates the drop-list or the ordinal vocabulary."""


@dataclass(frozen=True)
class FeatureSpec:
    """The frozen column contract of a trained model.

    Persisted next to the artifacts so serving can rebuild the identical matrix months
    later, including one-hot levels that may be absent from a single-row request.
    """

    columns: list[str]
    one_hot_levels: dict[str, list[str]]
    numeric: list[str]
    boolean: list[str]
    ordinal: list[str]

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "FeatureSpec":
        return cls(**d)


# --------------------------------------------------------------------------- loading
def load_projects(csv_path: str | pathlib.Path) -> pd.DataFrame:
    """Read projects.csv without destroying the literal string "None".

    `legal_dispute_stage` uses "None" to mean *no dispute on file* — ordinal level 0.
    Default `read_csv` NA handling turns it into NaN, the ordinal map then yields NaN, and
    the column collapses to near-zero importance. Reading the ordinal columns through a
    `str` converter bypasses NA coercion for exactly those columns and nothing else.
    """
    converters = {c: str for c in STRING_CONVERTER_COLUMNS}
    df = pd.read_csv(csv_path, converters=converters)
    if "legal_dispute_stage" in df.columns:
        n_none = int((df["legal_dispute_stage"] == "None").sum())
        if n_none == 0 and df["legal_dispute_stage"].isna().any():
            raise FeatureContractError(
                'legal_dispute_stage lost the literal "None" level during load — '
                "the Phase 1 finding-3 bug has been reintroduced."
            )
    return df


def load_frame_from_records(records: list[dict]) -> pd.DataFrame:
    """Serving entry point: rows already fetched from Postgres, no CSV parsing involved."""
    return pd.DataFrame.from_records(records)


# --------------------------------------------------------------------------- encoding
def _encode_ordinals(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    for col, mapping in ORDINAL_ENCODINGS.items():
        if col not in df.columns:
            continue
        raw = df[col].astype(str).str.strip()
        unknown = set(raw.unique()) - set(mapping)
        if unknown:
            raise FeatureContractError(
                f"{col}: unknown level(s) {sorted(unknown)} — extend the ordinal map in "
                "ml/src/features/schema.py rather than letting them fall through to NaN."
            )
        out[col] = raw.map(mapping).astype("int16")
    return out


def _encode_one_hot(
    df: pd.DataFrame, levels: dict[str, list[str]] | None
) -> tuple[pd.DataFrame, dict[str, list[str]]]:
    frames, resolved = [], {}
    for col in ONE_HOT_COLUMNS:
        if col not in df.columns:
            continue
        seen = sorted(df[col].astype(str).unique())
        use = levels[col] if levels and col in levels else seen
        resolved[col] = list(use)
        cat = pd.Categorical(df[col].astype(str), categories=use)
        dummies = pd.get_dummies(cat, prefix=col).astype("int8")
        dummies.index = df.index
        frames.append(dummies)
    if not frames:
        return pd.DataFrame(index=df.index), resolved
    return pd.concat(frames, axis=1), resolved


def _encode_numeric(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    for col in NUMERIC_COLUMNS:
        if col in df.columns:
            out[col] = pd.to_numeric(df[col], errors="coerce").astype("float32")
    for col in BOOLEAN_COLUMNS:
        if col in df.columns:
            s = df[col]
            if s.dtype == object:
                s = s.astype(str).str.strip().str.lower().map(
                    {"true": 1, "false": 0, "1": 1, "0": 0}
                )
            out[col] = pd.to_numeric(s, errors="coerce").fillna(0).astype("int8")
    return out


# --------------------------------------------------------------------------- public API
def build_feature_matrix(
    df: pd.DataFrame, spec: FeatureSpec | None = None
) -> tuple[pd.DataFrame, FeatureSpec]:
    """Turn raw project rows into the model's feature matrix.

    Pass `spec=None` at training time to derive the contract; pass the persisted spec at
    serving time so column order and one-hot levels are byte-identical to training.
    """
    assert_no_drop_list_columns(df, stage="input")

    ordinals = _encode_ordinals(df)
    numerics = _encode_numeric(df)
    one_hot, levels = _encode_one_hot(df, spec.one_hot_levels if spec else None)

    X = pd.concat([numerics, ordinals, one_hot], axis=1)

    if spec is None:
        spec = FeatureSpec(
            columns=list(X.columns),
            one_hot_levels=levels,
            numeric=[c for c in NUMERIC_COLUMNS if c in numerics.columns],
            boolean=[c for c in BOOLEAN_COLUMNS if c in numerics.columns],
            ordinal=list(ordinals.columns),
        )
    else:
        for missing in [c for c in spec.columns if c not in X.columns]:
            X[missing] = 0
        X = X[spec.columns]

    assert_no_drop_list_columns(X, stage="matrix")
    return X, spec


def assert_no_drop_list_columns(frame: pd.DataFrame, stage: str = "matrix") -> None:
    """Hard guard. At `stage="matrix"` any drop-list column present is a leak."""
    present = [c for c in DROP_LIST if c in frame.columns]
    if stage == "matrix" and present:
        raise FeatureContractError(
            f"drop-list column(s) reached the feature matrix: {present}. "
            "latent_risk_audit and top_driver_audit leak the label outright."
        )


def feature_names(spec: FeatureSpec) -> list[str]:
    return list(spec.columns)


def split_closed_ongoing(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """600 closed projects train the models; 300 ongoing projects are what we score."""
    closed_flag = df["is_closed_project"]
    if closed_flag.dtype == object:
        closed_flag = closed_flag.astype(str).str.lower().eq("true")
    closed = df[closed_flag.astype(bool)].copy()
    ongoing = df[~closed_flag.astype(bool)].copy()
    return closed, ongoing


def binary_target(df: pd.DataFrame) -> np.ndarray:
    y = df["is_delayed"]
    if y.dtype == object:
        y = y.astype(str).str.lower().eq("true")
    return y.astype(int).to_numpy()
