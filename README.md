# NII rate-shock model (illustrative)

A small, transparent Python model of how a stylised bank's **Net Interest Income** responds to cash-rate shocks — built as a demo of how financial models can live in GitHub: assumptions in config, logic in a tested module, the narrative in a Jupyter notebook, and checks that run automatically on every change.

> All balances, margins and betas are made up for demonstration. They do not represent any real institution.

**Start here → [`notebooks/nii_stress_demo.ipynb`](notebooks/nii_stress_demo.ipynb)** (GitHub renders it with all charts and tables).

## What the model does

- Holds a 10-line balance sheet constant for 24 months.
- Each line earns or pays `max(margin + beta × reference rate, floor)`.
- Repricing: a line with `reprice_months = T` is a rolling book where 1/T resets each month, so its reference rate is the trailing T-month average of the cash rate.
- Scenarios: base, ±200bp instantaneous, +200bp ramped over 12 months — plus a −300 to +300bp shock ladder and a deposit-beta sensitivity in the notebook.

## Repo layout

```
config/base.yaml          all assumptions (edit numbers here, not in code)
src/nii_model/model.py    model logic — small, documented functions
tests/                    pytest unit tests + a check that the notebook runs
notebooks/                the demo notebook with results and commentary
.github/workflows/ci.yml  runs the tests on every push and pull request
```

## Run it yourself

```bash
git clone https://github.com/<your-username>/nii-stress-model.git
cd nii-stress-model
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest                      # 12 tests should pass
jupyter lab notebooks/      # open and run the notebook
```

Or click **Code → Codespaces → Create codespace** on GitHub to get a ready-made environment in the browser with nothing to install.

## Why structure a model like this?

| Spreadsheet habit | Repo equivalent |
|---|---|
| Inputs tab | `config/base.yaml` |
| Calculation tabs | `src/nii_model/model.py` |
| Check cells / reconciliations | `tests/` — run automatically by GitHub Actions |
| "v3_final_FINAL.xlsx" | Git history: every change is a commit with a message and a diff |
| Reviewer comments | Pull requests: changes are reviewed line by line before merging |

## Ideas to extend

See the last cell of the notebook — each one (structural hedge, non-parallel shocks, deposit migration, EVE, loading data from Excel) is a good self-contained exercise for working with an AI coding assistant on a branch and reviewing the result as a pull request.

## Licence

MIT
