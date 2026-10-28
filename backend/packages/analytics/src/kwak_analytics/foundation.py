"""The forecast's foundation models (spec §4.14 F-FCT-3, 7): Chronos-2 and TimesFM 2.5, zero-shot.

Optional: only an image built with the `foundation` extra carries PyTorch, the two libraries and
the weights. The weights are fetched when the image is built (`python -m kwak_analytics.foundation
fetch DIR`), at a pinned revision whose files are checked against their recorded checksums, and
read offline from `KWAK_FOUNDATION_DIR`: nothing is downloaded nor sent when a forecast runs.
Without them, `available()` is false and the forecast runs on the other candidates.
"""

import hashlib
import logging
import os
import sys
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

CHRONOS = "chronos_2"
TIMESFM = "timesfm"
NAMES = (CHRONOS, TIMESFM)
"""From the simplest: the smaller model first (F-FCT-3)."""

CONTEXT = 60
"""The months a forecast reads, at most: the history's own limit."""
THREADS = 4
"""Fixed: PyTorch's results on the processor may change in the last digits with the threads."""
BATCH = 32


@dataclass(frozen=True)
class Weights:
    repo: str
    revision: str
    files: dict[str, str]
    """Each file's SHA-256."""


WEIGHTS = {
    CHRONOS: Weights(
        "amazon/chronos-2",
        "29ec3766d36d6f73f0696f85560a422f50e8498c",
        {
            "config.json": "ef1143bfdc9c0376d9a056eefca46cb4b1ec3d0ffacd541ff56feb40fb708031",
            "model.safetensors": "ddcda3c7508bf2528087723e98a20707cc04b7f370ae275a9fd88078ddba4f42",
        },
    ),
    TIMESFM: Weights(
        "google/timesfm-2.5-200m-pytorch",
        "1d952420fba87f3c6dee4f240de0f1a0fbc790e3",
        {
            "config.json": "cd3315b760d5cc7e278d7afdf41b897031ced888fc6c115bd9b3ac0ea2c47408",
            "model.safetensors": "2f776efe6245e42b24bc4153ffdf61810140210e4bd3b01fb21f7aa779ab6ce8",
        },
    ),
}


def directory() -> Path | None:
    found = os.environ.get("KWAK_FOUNDATION_DIR")
    return Path(found) if found else None


def revisions() -> dict[str, str]:
    """The models taking part and their revisions, shown on the page; empty without them."""
    return {name: WEIGHTS[name].revision[:12] for name in NAMES} if available() else {}


def available() -> bool:
    if _failed:
        return False
    root = directory()
    if root is None or not all(
        (root / name / file).is_file() for name, w in WEIGHTS.items() for file in w.files
    ):
        return False
    try:
        import chronos  # noqa: F401
        import timesfm  # noqa: F401
        import torch  # noqa: F401
    except ImportError:
        return False
    return True


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def fetch(root: Path) -> None:
    """At build time: each model's files at its revision, checked against their checksums."""
    from huggingface_hub import hf_hub_download

    for name, w in WEIGHTS.items():
        for file, expected in w.files.items():
            path = Path(hf_hub_download(w.repo, file, revision=w.revision, local_dir=root / name))
            if (found := _sha256(path)) != expected:
                raise SystemExit(f"{w.repo}/{file}: checksum {found}, expected {expected}")


_models: dict[str, Any] = {}
_failed = False
"""A load that raised: the forecast then runs without the models (F-FCT-7)."""
_lock = threading.Lock()

DECILES = [k / 10 for k in range(1, 10)]
"""Chronos-2 gives no mean (its "mean" is its median): the average of its deciles stands for it."""
CHRONOS_BATCH = 256


def _load() -> dict[str, Any] | None:
    """Both models, or None when either failed to load; never retried."""
    global _failed
    with _lock:
        if _models or _failed:
            return _models or None
        os.environ["HF_HUB_OFFLINE"] = "1"
        try:
            import timesfm
            import torch
            from chronos import BaseChronosPipeline

            torch.set_num_threads(THREADS)
            root = directory()
            assert root is not None  # noqa: S101 (callers check available())
            chronos = BaseChronosPipeline.from_pretrained(
                str(root / CHRONOS), device_map="cpu", torch_dtype=torch.float32
            )
            tfm = timesfm.TimesFM_2p5_200M_torch.from_pretrained(str(root / TIMESFM))
            tfm.compile(
                timesfm.ForecastConfig(
                    max_context=64,
                    max_horizon=16,
                    normalize_inputs=True,
                    use_continuous_quantile_head=True,
                    fix_quantile_crossing=True,
                    # Batched, or one series at a time: 10 times slower. Fixed, since the
                    # batch changes the last float digits.
                    per_core_batch_size=BATCH,
                )
            )
        except Exception:
            logger.exception("the foundation models failed to load; forecasting without them")
            _failed = True
            return None
        _models.update({CHRONOS: chronos, TIMESFM: tfm})
        return _models


def forecast(contexts: Sequence[Sequence[float]], horizon: int) -> dict[str, np.ndarray] | None:
    """Each model's mean for every context, `horizon` months ahead: (contexts, horizon); None
    when the models failed to load. The mean, not the median, so that sums over months and
    categories add up (F-FCT-3)."""
    models = _load()
    if models is None:
        return None
    import torch

    with _lock, torch.inference_mode():
        torch.set_num_threads(THREADS)  # per thread: the server answers in several
        torch.manual_seed(0)  # the models draw nothing; kept so a future version stays repeatable
        tensors = [torch.tensor(c[-CONTEXT:], dtype=torch.float32) for c in contexts]
        quantiles, _ = models[CHRONOS].predict_quantiles(
            tensors,
            prediction_length=horizon,
            quantile_levels=DECILES,
            batch_size=CHRONOS_BATCH,
        )
        q = torch.cat(quantiles) if isinstance(quantiles, list) else quantiles
        chronos = np.asarray(q.mean(dim=-1).cpu().numpy(), dtype=np.float64)
        chronos = chronos.reshape(len(contexts), -1)
        # TimesFM's quantiles: its mean first, then the deciles 0.1 to 0.9.
        _, tq = models[TIMESFM].forecast(
            horizon=horizon, inputs=[np.asarray(c[-CONTEXT:], dtype=np.float32) for c in contexts]
        )
        tfm = np.asarray(tq[..., 0], dtype=np.float64)
    return {CHRONOS: chronos[:, :horizon], TIMESFM: tfm[:, :horizon]}


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "fetch":
        raise SystemExit("usage: python -m kwak_analytics.foundation fetch DIR")
    fetch(Path(sys.argv[2]))
