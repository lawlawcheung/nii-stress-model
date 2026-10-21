"""Illustrative NII rate-shock model."""

from .model import (
    Line,
    balance_sheet_table,
    check_balances,
    delta_by_line,
    lines_from_config,
    load_config,
    nii_summary,
    project_nii,
    rate_path,
    reference_rate,
    run_scenarios,
    scenario_paths,
)

__all__ = [
    "Line",
    "balance_sheet_table",
    "check_balances",
    "delta_by_line",
    "lines_from_config",
    "load_config",
    "nii_summary",
    "project_nii",
    "rate_path",
    "reference_rate",
    "run_scenarios",
    "scenario_paths",
]
