"""Phase 2 exit criterion — all seven checks, run for real, exits non-zero on failure.

    python scripts/verify_phase2.py

Mirrors scripts/verify_phase1.py in spirit: nothing here is asserted from memory, every
number is recomputed from the artifacts on disk and the CSVs they were trained on.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml.src.explainability import RiskExplainer                     # noqa: E402
from ml.src.features import (                                       # noqa: E402
    load_projects,
    split_closed_ongoing,
    succession_risk,
)
from ml.src.models import registry as reg                           # noqa: E402

DATA = ROOT / "ml" / "data"
RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(ok), detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def main() -> int:
    print("=" * 78)
    print("BhoomiRakshak — Phase 2 exit criterion")
    print("=" * 78)

    version = reg.active_version()
    vdir = reg.version_dir(version)
    meta = reg.read_json(vdir / "metadata.json")
    card = reg.read_json(vdir / f"report_card_{version}.json")
    print(f"active model version: {version}\nregistry: {vdir}\n")

    # ------------------------------------------------------ 1. two versioned artifacts
    print("1. Two versioned artifacts written by `python -m ml.src.training.train`")
    a = vdir / "model_a_is_delayed.json"
    b = vdir / "model_b_delay_stage.json"
    spec = vdir / "feature_spec.json"
    cal = vdir / "model_a_calibrator.joblib"
    check(
        "Model A + Model B + feature spec + calibrator on disk",
        all(p.exists() for p in (a, b, spec, cal)),
        f"{a.name} ({a.stat().st_size:,} B), {b.name} ({b.stat().st_size:,} B)",
    )
    check(
        "version string is absolute-dated and recorded in metadata",
        meta["model_version"] == version and version.startswith("v20"),
        version,
    )

    # ------------------------------------------------------------------- 2. binary AUC
    print("\n2. Report card — binary AUC >= 0.85")
    auc = card["model_a_is_delayed"]["auc"]
    check("5-fold out-of-fold AUC", auc >= 0.85, f"AUC {auc} (accuracy {card['model_a_is_delayed']['accuracy']})")

    # ------------------------------------------------------------- 3. stage accuracy
    print("\n3. Report card — 5-class stage accuracy >= 2x the majority baseline")
    s = card["model_b_delay_stage"]
    check(
        "stage accuracy vs baseline",
        s["ratio_to_baseline"] >= 2.0,
        f"{s['accuracy']} vs baseline {s['majority_baseline']} = {s['ratio_to_baseline']}x (n={s['n']})",
    )

    # ---------------------------------------------------------------- 4. drop-list test
    print("\n4. Unit test — no drop-list column in the feature matrix")
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "ml/tests", "-q", "--no-header", "-p", "no:warnings"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    tail = [l for l in r.stdout.strip().splitlines() if l.strip()][-1] if r.stdout.strip() else ""
    check("ml/tests suite (includes the drop-list assertions)", r.returncode == 0, tail)

    # -------------------------------------------------------- 5. ordinal importances
    print("\n5. title_clarity_status and legal_dispute_stage carry non-zero importance")
    imp = {row["feature"]: row["gain_share"] for row in card["model_a_top_importance"]}
    for col in ("title_clarity_status", "legal_dispute_stage"):
        v = imp.get(col, 0.0)
        check(f"{col} gain share", v > 0.01, f"{v}")
    projects = load_projects(DATA / "projects.csv")
    check(
        'literal "None" preserved in legal_dispute_stage',
        int((projects.legal_dispute_stage == "None").sum()) > 0
        and int(projects.legal_dispute_stage.isna().sum()) == 0,
        f'{int((projects.legal_dispute_stage == "None").sum())} rows at ordinal level 0',
    )

    # ------------------------------------------------------------------- 6. SHAP top-3
    print("\n6. SHAP top-3 factors, officer language, three hand-picked projects")
    explainer = RiskExplainer.from_registry(version)
    _, ongoing = split_closed_ongoing(projects)
    ongoing = ongoing.reset_index(drop=True)
    suc = succession_risk(pd.read_csv(DATA / "succession_claims.csv"))
    high_suc = set(suc[suc.succession_risk_band == "High"].ulpin)

    picks = {
        "compensation-driven": ongoing.sort_values(
            "compensation_gap_pct", ascending=False
        ).iloc[0],
        "litigation-driven": ongoing[ongoing.court_stay_flag.astype(str).str.lower() == "true"]
        .sort_values("no_legal_disputes", ascending=False)
        .iloc[0],
        "succession-driven": ongoing[ongoing.ulpin.isin(high_suc)]
        .sort_values("ownership_fragmentation_index", ascending=False)
        .iloc[0],
    }

    sensible = True
    for label, row in picks.items():
        exp = explainer.explain_project(row)
        print(f"\n   --- {label} · {row.ulpin} · {row.project_name}")
        print(f"       {row.district}, {row.state} · stage: {row.approval_stage}")
        print(f"       calibrated risk {exp.risk_probability:.3f}")
        for k, f in enumerate(exp.top_factors(3), 1):
            print(
                f"       {k}. {f.display_label}\n"
                f"          {f.direction}, {f.contribution_pct:+.1f}% of this file's risk "
                f"[{f.group}]"
            )
        if label == "succession-driven":
            band = suc[suc.ulpin == row.ulpin].iloc[0]
            print(f"       succession (rule, not model): {band.succession_risk_band} — {band.succession_reason}")
        top = exp.top_factors(3)
        if len(top) != 3 or any(f.display_label.strip() == f.feature for f in top):
            sensible = False
    print()
    check("three explanations returned, each with three named factors", sensible)

    # ------------------------------------------------------- 7. succession rule parity
    print("\n7. Succession band matches the seeded table for all 362 parcels")
    seeded = pd.read_csv(DATA / "succession_risk.csv")
    computed = succession_risk(pd.read_csv(DATA / "succession_claims.csv"))
    m = seeded.merge(computed, on="ulpin", suffixes=("_s", "_c"))
    band_ok = (m.succession_risk_band_s == m.succession_risk_band_c).all()
    reason_ok = (m.succession_reason_s == m.succession_reason_c).all()
    check(
        "band and reason identical to generate_dataset.py",
        len(m) == len(seeded) == 362 and band_ok and reason_ok,
        f"{len(m)}/362 parcels, "
        + str(computed.succession_risk_band.value_counts().to_dict()),
    )

    # ---------------------------------------------------------------------- summary
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print("\n" + "=" * 78)
    print(f"Phase 2 exit criterion: {passed}/{len(RESULTS)} checks PASS")
    print("=" * 78)
    for name, ok, _ in RESULTS:
        if not ok:
            print(f"  FAILED: {name}")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
