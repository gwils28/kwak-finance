# Forecasting study

The study behind the app's cash-flow forecast (`docs/SPECIFICATIONS.md` §4.14): statistical,
machine-learning and foundation models compared on monthly household spending, with
probabilistic forecasts, explainability and causal inference.

**Synthetic data only.** The notebooks never read `data/` nor the app's database: every series
comes from `synthetic.py` (a seeded panel of 200 fictitious French households) or from the app's
demo household (`kwak_core.demo`).

## Set up

```bash
cd notebooks/forecasting
uv sync                      # its own environment: PyTorch, Chronos, TimesFM, Nixtla, skforecast, SHAP, Jupyter
uv run jupyter lab
```

This is a uv project of its own, apart from the backend workspace, so the app's image never
carries PyTorch nor the models. It depends on `kwak-core` and `kwak-analytics` by path, so the
notebooks run the app's real code.

- **GPU**: notebook 05 (and 09) use CUDA when available (tested on an RTX 5070 laptop, 8 GB);
  on a CPU they still run, more slowly (minutes).
- **Model weights** (Chronos-Bolt, Chronos-2, TimesFM 2.5) are downloaded once from the Hugging
  Face hub into its cache (`~/.cache/huggingface`), never into the repository. Nothing else is
  sent anywhere; no cloud model is used.
- Expensive runs are cached in `cache/` (git-ignored). Delete it to recompute everything (about
  10 minutes with a GPU).

## Run

```bash
for nb in 0*.ipynb; do uv run jupyter nbconvert --to notebook --execute --inplace "$nb"; done
```

## Reading order

| Notebook | Content |
|---|---|
| `00_overview` | The question, the constraints, the protocol, the headline results |
| `01_data` | The synthetic panel and the demo household: lengths, intermittency, seasonality, fixed shares |
| `02_protocol_and_metrics` | Rolling origins, MASE/RMSSE/WAPE/bias, coverage/MSIS/pinball/CRPS, baselines, tests |
| `03_statistical` | statsforecast models; per-category winners; the 24-month rule; the selection margin |
| `04_machine_learning` | mlforecast and skforecast; global, local and per-household LightGBM |
| `05_foundation_models` | Chronos-Bolt, Chronos-2 and TimesFM 2.5, zero-shot; cost |
| `06_probabilistic` | The app's conformal bands against model-based and foundation-model quantiles |
| `07_explainability` | TreeSHAP, the app's contributions on the demo, ETS shapes |
| `08_causal_inference` | Did a budget target lower the spending? Counterfactuals, DiD, placebos |
| `09_conclusion` | The app's pipeline on held-out years; synthesis and recommendations |

`synthetic.py` draws the panel; `study.py` holds the protocol and metrics every notebook shares.
