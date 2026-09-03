"""ml.src.features — the single feature-definition module.

Imported by ml.src.training (Phase 2) and by backend/app/services (Phase 3). The backend
must never rebuild features itself.
"""

from .build import (
    FeatureContractError,
    FeatureSpec,
    assert_no_drop_list_columns,
    binary_target,
    build_feature_matrix,
    feature_names,
    load_frame_from_records,
    load_projects,
    split_closed_ongoing,
)
from .derived import (
    compensation_gap_index,
    compute_all,
    litigation_propensity_score,
    succession_risk,
)
from .schema import (
    APPROVAL_STAGE_ORDER,
    BINARY_TARGET,
    BOOLEAN_COLUMNS,
    CLEARANCE_ORDER,
    DELAY_STAGE_CLASSES,
    DERIVED_SCORE_COLUMNS,
    DROP_LIST,
    LEGAL_DISPUTE_STAGE_ORDER,
    NUMERIC_COLUMNS,
    ONE_HOT_COLUMNS,
    ORDINAL_ENCODINGS,
    STAGE_NOT_APPLICABLE,
    STAGE_TARGET,
    TITLE_CLARITY_ORDER,
)

__all__ = [
    "APPROVAL_STAGE_ORDER",
    "BINARY_TARGET",
    "BOOLEAN_COLUMNS",
    "CLEARANCE_ORDER",
    "DELAY_STAGE_CLASSES",
    "DERIVED_SCORE_COLUMNS",
    "DROP_LIST",
    "FeatureContractError",
    "FeatureSpec",
    "LEGAL_DISPUTE_STAGE_ORDER",
    "NUMERIC_COLUMNS",
    "ONE_HOT_COLUMNS",
    "ORDINAL_ENCODINGS",
    "STAGE_NOT_APPLICABLE",
    "STAGE_TARGET",
    "TITLE_CLARITY_ORDER",
    "assert_no_drop_list_columns",
    "binary_target",
    "build_feature_matrix",
    "compensation_gap_index",
    "compute_all",
    "feature_names",
    "litigation_propensity_score",
    "load_frame_from_records",
    "load_projects",
    "split_closed_ongoing",
    "succession_risk",
]
