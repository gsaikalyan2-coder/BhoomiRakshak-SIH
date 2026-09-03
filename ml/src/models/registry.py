"""Versioned model registry.

Layout under MODEL_REGISTRY_PATH (default ./ml/experiments/registry):

    registry/
      LATEST                       <- plain text, one line: the active version string
      v2026-08-23T18-40-11/
        model_a_is_delayed.json    <- XGBoost booster, JSON (portable across xgboost 2.x)
        model_a_calibrator.joblib  <- isotonic calibrator fitted on out-of-fold predictions
        model_b_delay_stage.json
        feature_spec.json          <- the frozen column contract
        metadata.json              <- versions, row counts, metrics, class order, git-free
        derived_scores.parquet     <- + .csv, one row per project
        report_card.md / .json     <- written by ml.src.evaluation

Serving (Phase 3) resolves ACTIVE_MODEL_VERSION from .env and loads exactly this directory.
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib

DEFAULT_REGISTRY = pathlib.Path("ml/experiments/registry")


def registry_root(path: str | pathlib.Path | None = None) -> pathlib.Path:
    import os

    root = pathlib.Path(path or os.environ.get("MODEL_REGISTRY_PATH", DEFAULT_REGISTRY))
    root.mkdir(parents=True, exist_ok=True)
    return root


def new_version(now: dt.datetime | None = None) -> str:
    """Absolute-dated version string, e.g. `v2026-08-23T18-40-11`. Never relative."""
    now = now or dt.datetime.now()
    return "v" + now.strftime("%Y-%m-%dT%H-%M-%S")


def version_dir(version: str, path: str | pathlib.Path | None = None) -> pathlib.Path:
    d = registry_root(path) / version
    d.mkdir(parents=True, exist_ok=True)
    return d


def set_active(version: str, path: str | pathlib.Path | None = None) -> pathlib.Path:
    p = registry_root(path) / "LATEST"
    p.write_text(version + "\n", encoding="utf-8")
    return p


def active_version(path: str | pathlib.Path | None = None) -> str:
    import os

    env = os.environ.get("ACTIVE_MODEL_VERSION", "").strip()
    if env and env != "ENTER_YOUR_VALUE_HERE":
        return env
    latest = registry_root(path) / "LATEST"
    if not latest.exists():
        raise FileNotFoundError(
            "No active model version. Run `python -m ml.src.training.train` first, "
            "or set ACTIVE_MODEL_VERSION in .env."
        )
    return latest.read_text(encoding="utf-8").strip()


def write_json(target: pathlib.Path, payload: dict) -> pathlib.Path:
    target.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return target


def read_json(target: pathlib.Path) -> dict:
    return json.loads(target.read_text(encoding="utf-8"))
