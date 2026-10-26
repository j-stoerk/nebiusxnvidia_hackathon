"""Optional CPU foundation-model experiment; run in a separate ML environment.

Weights/cache go to --cache, never into the repo or the application environment.
Only public checkpoints are downloaded; no inference service or API key is used.
"""
import argparse
import gc
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[1]
MODELS = {
    "chronos_tiny": ("amazon/chronos-bolt-tiny", "a0e552de83495b5c28c14c71c374f3e33280b340"),
    "chronos_small": ("amazon/chronos-bolt-small", "772f3d25d38aec6d914c8949dab4462e2d46f5d8"),
    "timesfm_2_5": ("google/timesfm-2.5-200m-pytorch", "1d952420fba87f3c6dee4f240de0f1a0fbc790e3"),
}


def predict(name, contexts):
    import numpy as np
    import torch
    model_id, revision = MODELS[name]
    began = time.perf_counter()
    if name.startswith("chronos"):
        from chronos import BaseChronosPipeline
        model = BaseChronosPipeline.from_pretrained(model_id, revision=revision, token=False, device_map="cpu", torch_dtype=torch.float32)
        loaded = time.perf_counter()
        with torch.inference_mode():
            values = model.predict(torch.tensor(contexts, dtype=torch.float32), prediction_length=24).cpu().numpy()
        # Chronos-Bolt's nine native quantiles are 0.1, ..., 0.9.
        low, point, high = values[:, 0], values[:, 4], values[:, 8]
    else:
        import timesfm
        model = timesfm.TimesFM_2p5_200M_torch.from_pretrained(model_id, revision=revision, token=False, torch_compile=False)
        model.compile(timesfm.ForecastConfig(max_context=512, max_horizon=128, per_core_batch_size=4,
            normalize_inputs=True, use_continuous_quantile_head=True, force_flip_invariance=False,
            infer_is_positive=False, fix_quantile_crossing=True))
        loaded = time.perf_counter()
        point, quantiles = model.forecast(horizon=24, inputs=list(contexts))
        low, high = quantiles[:, :, 1], quantiles[:, :, 9]
    result = {"point": np.asarray(point).reshape(-1).tolist(), "q10": np.asarray(low).reshape(-1).tolist(), "q90": np.asarray(high).reshape(-1).tolist(),
              "load_seconds": round(loaded-began, 3), "inference_seconds": round(time.perf_counter()-loaded, 3), "checkpoint": model_id, "revision": revision}
    del model
    gc.collect()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", default="D:/ChargeWise_Cache/huggingface")
    parser.add_argument("--models", nargs="+", choices=MODELS, default=list(MODELS))
    parser.add_argument("--output", type=Path, default=ROOT/".cache/foundation-predictions.json")
    parser.add_argument("--resume", action="store_true", help="Retain completed models with matching inputs/protocol")
    args = parser.parse_args()
    os.environ.update(HF_HOME=args.cache, HF_HUB_DISABLE_IMPLICIT_TOKEN="1", HF_HUB_DISABLE_TELEMETRY="1", HF_HUB_DISABLE_XET="1", TOKENIZERS_PARALLELISM="false")
    # Prevent inherited provider credentials from being used by a research library.
    for key in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "NEBIUS_API_KEY"):
        os.environ.pop(key, None)
    import numpy as np
    import pandas as pd
    import torch
    torch.set_num_threads(6)
    torch.manual_seed(20261026)
    path = ROOT/"data/external/required/2019-04-01_2019-10-01/germany_day_ahead_eur_mwh_hourly.csv"
    frame = pd.read_csv(path)
    y = frame.price_eur_per_mwh.to_numpy(dtype=float)/1000
    start = int(len(y)//24*.8)*24
    contexts = np.stack([y[origin-512:origin] for origin in range(start, len(y), 24)])
    result = {"input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "test_start": frame.timestamp.iloc[start],
        "protocol_sha256": hashlib.sha256((ROOT/"docs/foundation-forecasting.md").read_bytes()).hexdigest(), "context_hours": 512, "horizon_hours": 24, "device": "CPU", "models": {}, "failures": {},
        "versions": {name: importlib.metadata.version(name) for name in ("torch", "chronos-forecasting", "timesfm", "transformers")}}
    if args.resume and args.output.is_file():
        previous = json.loads(args.output.read_text(encoding="utf-8"))
        assert all(previous[k] == result[k] for k in ("input_sha256", "protocol_sha256", "versions"))
        result["models"] = previous["models"]
        result["resolved_setup_issues"] = previous.get("failures", {})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for name in args.models:
        print(f"Loading public checkpoint: {MODELS[name][0]}", flush=True)
        try:
            result["models"][name] = predict(name, contexts)
            print(f"Completed {name}: {result['models'][name]['inference_seconds']} seconds inference", flush=True)
        except Exception as exc:
            result["failures"][name] = str(exc)
            print(f"Model test failed: {name} ({type(exc).__name__})", flush=True)
        args.output.write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(f"Saved local prediction evidence: {args.output}")


if __name__ == "__main__":
    main()
