"""Phase 2 training entrypoint.

    python -m ml.src.training.train

Produces, under MODEL_REGISTRY_PATH/<version>/:
  model_a_is_delayed.json      Model A — binary `is_delayed`, 600 closed projects
  model_a_calibrator.joblib    isotonic calibration fitted on out-of-fold predictions
  model_b_delay_stage.json     Model B — 5-class `delay_stage`, conditional on delay
  feature_spec.json            frozen column contract, imported by serving in Phase 3
  metadata.json                versions, row counts, headline metrics, class order
  derived_scores.parquet/.csv  compensation gap · litigation propensity · succession band
  report_card_<version>.md/.json + calibration_<version>.png

and sets ACTIVE_MODEL_VERSION / MODEL_REGISTRY_PATH in the local .env.

Model A is trained on the 600 closed projects only. Model B is trained on the delayed
subset of those, because `delay_stage` is undefined for a project that did not slip.
"""

from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import re
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

from ..evaluation import (
    binary_metrics,
    calibration_plot,
    multiclass_metrics,
    oof_binary,
    oof_multiclass,
    write_report_card,
)
from ..features import (
    DELAY_STAGE_CLASSES,
    STAGE_NOT_APPLICABLE,
    binary_target,
    build_feature_matrix,
    compute_all,
    load_projects,
    split_closed_ongoing,
)
from ..models import registry as reg
from ..models.definitions import make_model_a, make_model_b

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "ml" / "data"
EXPERIMENTS = REPO_ROOT / "ml" / "experiments"


def _gain_importance(model, columns: list[str]) -> list[tuple[str, float]]:
    booster = model.get_booster()
    raw = booster.get_score(importance_type="gain")
    total = sum(raw.values()) or 1.0
    # xgboost names features f0, f1, … when fitted from a numpy-backed frame
    named: dict[str, float] = {}
    for k, v in raw.items():
        if k in columns:
            named[k] = v / total
        else:
            m = re.fullmatch(r"f(\d+)", k)
            if m and int(m.group(1)) < len(columns):
                named[columns[int(m.group(1))]] = v / total
    return sorted(named.items(), key=lambda kv: kv[1], reverse=True)


def _update_env(env_path: pathlib.Path, values: dict[str, str]) -> None:
    if not env_path.exists():
        env_path.write_text(
            "\n".join(f"{k}={v}" for k, v in values.items()) + "\n", encoding="utf-8"
        )
        return
    lines = env_path.read_text(encoding="utf-8").splitlines()
    seen = set()
    for i, line in enumerate(lines):
        for k, v in values.items():
            if re.match(rf"^\s*{re.escape(k)}\s*=", line):
                lines[i] = f"{k}={v}"
                seen.add(k)
    for k, v in values.items():
        if k not in seen:
            lines.append(f"{k}={v}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Train BhoomiRakshak Models A and B.")
    ap.add_argument("--data-dir", default=str(DATA_DIR))
    ap.add_argument("--registry", default=None, help="overrides MODEL_REGISTRY_PATH")
    ap.add_argument("--env-file", default=str(REPO_ROOT / ".env"))
    ap.add_argument("--no-env-write", action="store_true")
    args = ap.parse_args(argv)

    data_dir = pathlib.Path(args.data_dir)
    registry_path = args.registry or str(EXPERIMENTS / "registry")
    run_date = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    version = reg.new_version()

    print(f"BhoomiRakshak — Phase 2 training run {version}  ({run_date})")
    print("=" * 78)

    # ------------------------------------------------------------------ 1. load
    projects = load_projects(data_dir / "projects.csv")
    claims = pd.read_csv(data_dir / "succession_claims.csv")
    closed, ongoing = split_closed_ongoing(projects)
    print(f"[1/7] loaded {len(projects)} projects — {len(closed)} closed, {len(ongoing)} ongoing")
    print(
        "      legal_dispute_stage 'None' rows preserved: "
        f"{int((projects.legal_dispute_stage == 'None').sum())}"
    )

    # ------------------------------------------------------- 2. feature matrix
    X_closed, spec = build_feature_matrix(closed)
    y = binary_target(closed)
    print(f"[2/7] feature matrix {X_closed.shape} — {len(spec.columns)} columns, 0 drop-list")

    # ------------------------------------------------------------- 3. Model A
    print("[3/7] Model A — binary is_delayed, 5-fold CV then full refit")
    oof_a = oof_binary(X_closed, y)
    m_binary = binary_metrics(y, oof_a, closed["state"].reset_index(drop=True))
    model_a = make_model_a()
    model_a.fit(X_closed, y)

    calibrator = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
    calibrator.fit(oof_a, y)
    print(f"      AUC {m_binary['auc']}  accuracy {m_binary['accuracy']}  Brier {m_binary['brier']}")

    # ------------------------------------------------------------- 4. Model B
    print("[4/7] Model B — 5-class delay_stage, conditional on delay")
    delayed = closed[
        closed["delay_stage"].notna()
        & (closed["delay_stage"].astype(str) != STAGE_NOT_APPLICABLE)
    ].copy()
    classes = [c for c in DELAY_STAGE_CLASSES if c in set(delayed["delay_stage"])]
    unknown = sorted(set(delayed["delay_stage"]) - set(classes))
    if unknown:
        raise ValueError(f"delay_stage carries unexpected class(es): {unknown}")
    idx = {c: i for i, c in enumerate(classes)}
    y_stage = delayed["delay_stage"].map(idx).to_numpy()
    X_stage, _ = build_feature_matrix(delayed, spec)

    oof_b = oof_multiclass(X_stage, y_stage, len(classes))
    m_stage = multiclass_metrics(
        y_stage, oof_b, classes, delayed["state"].reset_index(drop=True)
    )
    model_b = make_model_b(len(classes))
    model_b.fit(X_stage, y_stage)
    print(
        f"      accuracy {m_stage['accuracy']}  baseline {m_stage['majority_baseline']}"
        f"  ratio {m_stage['ratio_to_baseline']}x  (n={m_stage['n']})"
    )

    # --------------------------------------------------------- 5. derived scores
    print("[5/7] derived scores — compensation gap, litigation propensity, succession")
    derived = compute_all(projects, claims)
    bands = derived["succession_risk_band"].value_counts().to_dict()
    print(f"      succession bands: {bands}")

    # ------------------------------------------------------------- 6. persist
    d = reg.version_dir(version, registry_path)
    model_a.save_model(d / "model_a_is_delayed.json")
    model_b.save_model(d / "model_b_delay_stage.json")
    joblib.dump(calibrator, d / "model_a_calibrator.joblib")
    reg.write_json(d / "feature_spec.json", spec.to_dict())

    imp_a = _gain_importance(model_a, list(X_closed.columns))
    imp_b = _gain_importance(model_b, list(X_stage.columns))

    derived.to_csv(d / "derived_scores.csv", index=False)
    try:
        derived.to_parquet(d / "derived_scores.parquet", index=False)
    except Exception as exc:                                    # pyarrow absent
        print(f"      (parquet skipped: {exc}; CSV written)")

    # score every ongoing project so Phase 3's batch job has a reference to check against
    X_ongoing, _ = build_feature_matrix(ongoing, spec)
    raw_ongoing = model_a.predict_proba(X_ongoing)[:, 1]
    cal_ongoing = np.clip(calibrator.predict(raw_ongoing), 0.0, 1.0)
    stage_proba = model_b.predict_proba(X_ongoing)
    scored = pd.DataFrame(
        {
            "ulpin": ongoing["ulpin"].to_numpy(),
            "risk_probability_raw": np.round(raw_ongoing, 5),
            "risk_probability": np.round(cal_ongoing, 5),
            "risk_band": pd.cut(
                cal_ongoing,
                bins=[-0.01, 0.40, 0.70, 1.01],
                labels=["Low", "Medium", "High"],
            ).astype(str),
            "predicted_delay_stage": [classes[i] for i in stage_proba.argmax(axis=1)],
            "delay_stage_confidence": np.round(stage_proba.max(axis=1), 4),
            "model_version": version,
        }
    )
    scored.to_csv(d / "ongoing_scores.csv", index=False)

    reg.write_json(
        d / "metadata.json",
        {
            "model_version": version,
            "run_date": run_date,
            "trained_by": "ml.src.training.train",
            "data_source": str(data_dir),
            "data_revision": "rev 3 (synthetic)",
            "n_projects": int(len(projects)),
            "n_closed_training": int(len(closed)),
            "n_ongoing_scored": int(len(ongoing)),
            "n_delayed_stage_training": int(len(delayed)),
            "feature_count": len(spec.columns),
            "delay_stage_classes": classes,
            "risk_bands": {"High": ">= 0.70", "Medium": "0.40 - 0.69", "Low": "< 0.40"},
            "metrics": {
                "binary_auc": m_binary["auc"],
                "binary_accuracy": m_binary["accuracy"],
                "binary_brier": m_binary["brier"],
                "stage_accuracy": m_stage["accuracy"],
                "stage_majority_baseline": m_stage["majority_baseline"],
                "stage_ratio_to_baseline": m_stage["ratio_to_baseline"],
            },
            "succession_band_counts": bands,
            "library_versions": {
                "xgboost": __import__("xgboost").__version__,
                "shap": __import__("shap").__version__,
                "scikit_learn": __import__("sklearn").__version__,
                "pandas": pd.__version__,
                "numpy": np.__version__,
            },
        },
    )
    reg.set_active(version, registry_path)
    print(f"[6/7] artifacts written to {d}")

    # --------------------------------------------------------- 7. report card
    png = d / f"calibration_{version}.png"
    calibration_plot(m_binary, png)
    md, js = write_report_card(
        version, run_date, m_binary, m_stage, imp_a, imp_b, d, png.name
    )
    # a stable copy at the experiments root, so the latest card is always easy to find
    (EXPERIMENTS / "report_card_latest.md").write_text(
        md.read_text(encoding="utf-8"), encoding="utf-8"
    )
    print(f"[7/7] report card {md}")

    if not args.no_env_write:
        _update_env(
            pathlib.Path(args.env_file),
            {
                "MODEL_REGISTRY_PATH": registry_path.replace("\\", "/"),
                "ACTIVE_MODEL_VERSION": version,
            },
        )
        print(f"      .env updated — ACTIVE_MODEL_VERSION={version}")

    print("=" * 78)
    ok_a = m_binary["auc"] >= 0.85
    ok_b = m_stage["ratio_to_baseline"] >= 2.0
    print(f"binary AUC          {m_binary['auc']:.4f}   (>= 0.85)  {'PASS' if ok_a else 'FAIL'}")
    print(
        f"stage accuracy      {m_stage['accuracy']:.4f}   "
        f"({m_stage['ratio_to_baseline']:.2f}x baseline {m_stage['majority_baseline']:.4f})  "
        f"{'PASS' if ok_b else 'FAIL'}"
    )
    return 0 if (ok_a and ok_b) else 1


if __name__ == "__main__":
    sys.exit(main())
