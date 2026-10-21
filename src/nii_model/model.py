"""A deliberately simple Net Interest Income (NII) rate-shock model.

How it works
------------
* The balance sheet is **static**: every line keeps its balance for the whole
  horizon (a "constant balance sheet" assumption, as in a standard NII-at-risk
  run).
* Each line earns or pays::

      rate_t = max(margin + beta * reference_rate_t, floor)

  where ``beta`` is the pass-through of the cash rate (1.0 for loans, lower for
  deposits) and ``floor`` stops deposit rates going negative.
* ``reference_rate_t`` reflects **repricing**. A line with ``reprice_months=T``
  is treated as a rolling book where 1/T of the balance resets each month, so
  its reference rate is the average cash rate over the trailing T months.
  ``T=1`` means it reprices straight away; a 3-year fixed book (``T=36``) only
  gradually picks up a rate shock.
* Monthly interest = balance x rate / 12. NII = interest income - interest
  expense. Equity and non-interest-bearing assets earn/pay nothing.

All numbers in ``config/base.yaml`` are illustrative, not any real bank's.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

SIDES = ("asset", "liability", "equity")


@dataclass(frozen=True)
class Line:
    """One line of the balance sheet."""

    name: str
    side: str  # "asset", "liability" or "equity"
    balance: float  # $m
    margin: float = 0.0  # spread over beta x cash rate (decimal, 0.02 = 2%)
    beta: float = 0.0  # pass-through of the cash rate
    reprice_months: int = 1  # months for the whole book to reprice
    floor: float | None = None  # lowest rate the line can have (None = no floor)

    def __post_init__(self) -> None:
        if self.side not in SIDES:
            raise ValueError(f"{self.name}: side must be one of {SIDES}, got {self.side!r}")
        if self.balance < 0:
            raise ValueError(f"{self.name}: balance must be non-negative")
        if self.reprice_months < 1:
            raise ValueError(f"{self.name}: reprice_months must be at least 1")

    @property
    def sign(self) -> int:
        """+1 for income (assets), -1 for expense (liabilities), 0 for equity."""
        return {"asset": 1, "liability": -1, "equity": 0}[self.side]


# --------------------------------------------------------------------------- #
# Inputs
# --------------------------------------------------------------------------- #
def load_config(path: str | Path) -> dict:
    """Read the YAML assumptions file."""
    with open(path) as fh:
        return yaml.safe_load(fh)


def lines_from_config(config: dict) -> list[Line]:
    return [Line(**item) for item in config["balance_sheet"]]


def balance_sheet_table(lines: list[Line]) -> pd.DataFrame:
    """The balance sheet as a DataFrame (handy for display)."""
    return pd.DataFrame([vars(line) for line in lines]).set_index("name")


def check_balances(lines: list[Line], tolerance: float = 1e-6) -> None:
    """Raise if assets != liabilities + equity."""
    total = {side: sum(l.balance for l in lines if l.side == side) for side in SIDES}
    gap = total["asset"] - total["liability"] - total["equity"]
    if abs(gap) > tolerance:
        raise ValueError(
            f"Balance sheet does not balance: assets {total['asset']:,.0f} vs "
            f"liabilities + equity {total['liability'] + total['equity']:,.0f}"
        )


# --------------------------------------------------------------------------- #
# Rate scenarios
# --------------------------------------------------------------------------- #
def rate_path(
    start_rate: float,
    horizon_months: int,
    shock_bp: float = 0.0,
    ramp_months: int = 0,
    floor: float = 0.0,
) -> np.ndarray:
    """Monthly cash-rate path.

    ``ramp_months=0`` gives an instantaneous parallel shock from month 1;
    otherwise the shock builds in equal steps and is fully in place after
    ``ramp_months`` months.
    """
    months = np.arange(1, horizon_months + 1)
    shock = shock_bp / 10_000
    if ramp_months > 0:
        path = start_rate + shock * np.minimum(months / ramp_months, 1.0)
    else:
        path = np.full(horizon_months, start_rate + shock)
    return np.maximum(path, floor)


def scenario_paths(config: dict) -> pd.DataFrame:
    """Cash-rate path for every scenario in the config (rows = months)."""
    meta = config["meta"]
    paths = {
        name: rate_path(meta["start_cash_rate"], meta["horizon_months"], **(spec or {}))
        for name, spec in config["scenarios"].items()
    }
    df = pd.DataFrame(paths, index=pd.RangeIndex(1, meta["horizon_months"] + 1, name="month"))
    return df


def reference_rate(path: np.ndarray, start_rate: float, reprice_months: int) -> np.ndarray:
    """Average cash rate over the trailing ``reprice_months`` months.

    Months before the projection starts are assumed to sit at ``start_rate``
    (i.e. the book was in steady state when the shock hit).
    """
    history = np.full(reprice_months - 1, start_rate)
    padded = np.concatenate([history, path])
    window = np.ones(reprice_months) / reprice_months
    return np.convolve(padded, window, mode="valid")


# --------------------------------------------------------------------------- #
# Projection
# --------------------------------------------------------------------------- #
def project_nii(lines: list[Line], path: np.ndarray, start_rate: float) -> pd.DataFrame:
    """Monthly interest by line for one scenario.

    Returns a DataFrame (rows = months, columns = lines) of signed interest
    in $m: income positive, expense negative. ``.sum(axis=1)`` is NII.
    """
    out = {}
    for line in lines:
        if line.sign == 0:
            continue
        rate = line.margin + line.beta * reference_rate(path, start_rate, line.reprice_months)
        if line.floor is not None:
            rate = np.maximum(rate, line.floor)
        out[line.name] = line.sign * line.balance * rate / 12
    return pd.DataFrame(out, index=pd.RangeIndex(1, len(path) + 1, name="month"))


def run_scenarios(config: dict) -> dict[str, pd.DataFrame]:
    """Project every scenario. Returns {scenario name: monthly interest by line}."""
    lines = lines_from_config(config)
    check_balances(lines)
    start = config["meta"]["start_cash_rate"]
    paths = scenario_paths(config)
    return {name: project_nii(lines, paths[name].to_numpy(), start) for name in paths}


def nii_summary(results: dict[str, pd.DataFrame], base: str = "base") -> pd.DataFrame:
    """Annual NII per scenario and the change against the base case ($m and %)."""
    rows = {}
    for name, monthly in results.items():
        nii = monthly.sum(axis=1)
        years = nii.groupby((nii.index - 1) // 12 + 1).sum()
        rows[name] = {f"Year {y} NII": v for y, v in years.items()}
    summary = pd.DataFrame(rows).T
    for col in [c for c in summary.columns if c.endswith("NII")]:
        year = col.replace(" NII", "")
        summary[f"{year} ΔNII"] = summary[col] - summary.loc[base, col]
        summary[f"{year} ΔNII %"] = 100 * summary[f"{year} ΔNII"] / summary.loc[base, col]
    return summary


def delta_by_line(
    results: dict[str, pd.DataFrame], scenario: str, base: str = "base", year: int = 1
) -> pd.Series:
    """Which lines drive the change in NII for one scenario and year ($m)."""
    months = slice(12 * (year - 1) + 1, 12 * year)
    diff = results[scenario].loc[months].sum() - results[base].loc[months].sum()
    return diff.sort_values()
