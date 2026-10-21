"""Unit tests: run with `pytest` from the repo root."""

from pathlib import Path

import numpy as np
import pytest

from nii_model import (
    Line,
    check_balances,
    load_config,
    nii_summary,
    project_nii,
    rate_path,
    reference_rate,
    run_scenarios,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG = load_config(ROOT / "config" / "base.yaml")


# ---- inputs ---------------------------------------------------------------- #
def test_config_balance_sheet_balances():
    from nii_model import lines_from_config

    check_balances(lines_from_config(CONFIG))  # raises if it doesn't


def test_unbalanced_sheet_is_rejected():
    lines = [Line("Loan", "asset", 100), Line("Deposit", "liability", 90)]
    with pytest.raises(ValueError, match="does not balance"):
        check_balances(lines)


def test_bad_side_is_rejected():
    with pytest.raises(ValueError):
        Line("Oops", "asset_typo", 100)


# ---- rate paths ------------------------------------------------------------ #
def test_parallel_shock_is_immediate():
    path = rate_path(0.03, 12, shock_bp=200)
    assert np.allclose(path, 0.05)


def test_ramp_reaches_full_shock_at_end_of_ramp():
    path = rate_path(0.03, 24, shock_bp=200, ramp_months=12)
    assert path[0] == pytest.approx(0.03 + 0.02 / 12)
    assert path[11] == pytest.approx(0.05)
    assert np.allclose(path[12:], 0.05)


def test_cash_rate_is_floored_at_zero():
    assert rate_path(0.01, 6, shock_bp=-300).min() == 0.0


def test_reference_rate_phases_in_over_reprice_period():
    path = np.full(12, 0.05)  # shock from 3% to 5% in month 1
    ref = reference_rate(path, start_rate=0.03, reprice_months=4)
    # after 1 month a quarter of the book has repriced, after 4 months all of it
    assert ref[0] == pytest.approx(0.035)
    assert ref[3] == pytest.approx(0.05)


# ---- projection ------------------------------------------------------------ #
def test_nii_matches_hand_calculation():
    lines = [
        Line("Loan", "asset", 1200, margin=0.02, beta=1.0),
        Line("Deposit", "liability", 1000, margin=-0.01, beta=0.5, floor=0.0),
        Line("Equity", "equity", 200),
    ]
    monthly = project_nii(lines, np.full(12, 0.04), start_rate=0.04)
    # Loan: 1200 x (2% + 4%) = 72 a year; deposit: 1000 x (-1% + 2%) = 10 a year
    assert monthly.sum(axis=1).sum() == pytest.approx(72 - 10)


def test_deposit_floor_binds():
    lines = [Line("Deposit", "liability", 1000, margin=-0.02, beta=0.5, floor=0.0)]
    monthly = project_nii(lines, np.full(12, 0.01), start_rate=0.01)
    assert monthly.to_numpy().sum() == 0.0  # would be negative without the floor


def test_base_case_nii_is_flat():
    nii = run_scenarios(CONFIG)["base"].sum(axis=1)
    assert np.allclose(nii, nii.iloc[0])


def test_zero_shock_matches_base():
    config = {**CONFIG, "scenarios": {"base": {}, "zero": {"shock_bp": 0}}}
    summary = nii_summary(run_scenarios(config))
    assert summary.loc["zero", "Year 1 ΔNII"] == pytest.approx(0.0)
