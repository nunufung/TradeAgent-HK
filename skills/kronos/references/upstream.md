# Reviewed upstream

- Repository: https://github.com/shiyu-coder/Kronos
- Reviewed: 2026-10-24, Asia/Hong_Kong.
- Source commit: 67b630e67f6a18c9e9be918d9b4337c960db1e9a.
- [README](https://github.com/shiyu-coder/Kronos/blob/67b630e67f6a18c9e9be918d9b4337c960db1e9a/README.md).
- [Predictor implementation](https://github.com/shiyu-coder/Kronos/blob/67b630e67f6a18c9e9be918d9b4337c960db1e9a/model/kronos.py).
- [Requirements](https://github.com/shiyu-coder/Kronos/blob/67b630e67f6a18c9e9be918d9b4337c960db1e9a/requirements.txt).
- License: MIT, copyright (c) 2025 ShiYu; see UPSTREAM-LICENSE.txt.
- Paper: https://arxiv.org/abs/2508.02739

Upstream supplies model code, not a ready-made agent Skill. This package adds project-specific research instructions. It does not vendor models, install dependencies, download weights or generate forecasts on registration.

## Model pairs

| Model ID | Tokenizer ID | Maximum context |
| --- | --- | --- |
| NeoQuasar/Kronos-mini | NeoQuasar/Kronos-Tokenizer-2k | 2048 |
| NeoQuasar/Kronos-small | NeoQuasar/Kronos-Tokenizer-base | 512 |
| NeoQuasar/Kronos-base | NeoQuasar/Kronos-Tokenizer-base | 512 |

The reviewed README does not release Kronos-large weights. Do not promise availability. Source pinning does not pin Hugging Face weights: resolve and record their commit revisions separately.

## Isolated setup

Use Python 3.10+ in a separate tool directory outside application dependencies. Substitute a real absolute directory for the example:

```bash
git clone https://github.com/shiyu-coder/Kronos.git /absolute/tooling/Kronos
git -C /absolute/tooling/Kronos checkout --detach 67b630e67f6a18c9e9be918d9b4337c960db1e9a
python3 -m venv /absolute/tooling/Kronos/.venv
/absolute/tooling/Kronos/.venv/bin/python -m pip install -r /absolute/tooling/Kronos/requirements.txt
```

Review requirements and available hardware first. Run from the Kronos checkout or explicitly configure its import path: upstream imports classes from model. Do not install an unrelated PyPI package named kronos. Do not replace pandas or add torch to the daily environment to register this Skill. Qlib and fine-tuning packages are unnecessary for initial inference.

## Predictor API

This is an API sketch, not a standalone runner. Supply validated history, future_sessions, tokenizer_revision and model_revision first. Future sessions need a verified HKEX calendar and no future prices. The sketch assumes all six feature columns exist; see missing-feature behavior below.

```python
from model import Kronos, KronosTokenizer, KronosPredictor

tokenizer = KronosTokenizer.from_pretrained(
    "NeoQuasar/Kronos-Tokenizer-base", revision=tokenizer_revision
)
model = Kronos.from_pretrained(
    "NeoQuasar/Kronos-small", revision=model_revision
)
predictor = KronosPredictor(model, tokenizer, device="cpu", max_context=512)
forecast = predictor.predict(
    df=history[["open", "high", "low", "close", "volume", "amount"]],
    x_timestamp=history["timestamps"].reset_index(drop=True),
    y_timestamp=future_sessions.reset_index(drop=True),
    pred_len=len(future_sessions),
    T=1.0,
    top_k=0,
    top_p=0.9,
    sample_count=1,
    verbose=False,
)
```

Set Python, NumPy and torch seeds before sampling and record them. Device differences can still affect repeatability. Check returned timestamps, shape and candles before using results. Validate runtime compatibility with real smoke inference, not an import alone.

predict returns OHLC, volume and amount indexed by future timestamps. In the reviewed implementation, missing volume causes volume and amount to be zero-filled; when volume exists but amount is missing, amount is estimated as volume times mean OHLC. This estimate is not exchange turnover: provide actual amount when available or disclose the proxy. Disclose zero-filled missing features rather than presenting them as observed trades.

predict_batch requires equal history lengths and equal forecast lengths across series. Both APIs average sample_count paths internally; use separate calls with sample_count=1 for individual paths.
