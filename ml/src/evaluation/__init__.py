"""ml.src.evaluation — cross-validated report card generation."""

from .report import (
    N_SPLITS,
    binary_metrics,
    calibration_plot,
    multiclass_metrics,
    oof_binary,
    oof_multiclass,
    write_report_card,
)

__all__ = [
    "N_SPLITS",
    "binary_metrics",
    "calibration_plot",
    "multiclass_metrics",
    "oof_binary",
    "oof_multiclass",
    "write_report_card",
]
