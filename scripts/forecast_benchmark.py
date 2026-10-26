"""Chronological price-forecast and realized charging-cost check; no heavy models."""
from pathlib import Path
from datetime import timedelta
import hashlib
import json
import sys
import argparse
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.models import PricePoint, StationConfig
from backend.app.services.csv_validator import validate_sessions_csv
from backend.app.services.optimizer import optimize_schedule
from backend.app.services.cost_calculator import compute_metrics


def features(y, times):
    rows = []
    for t in range(168, len(y)):
        origin = t // 24 * 24
        day, week = y[origin-24:origin], y[origin-168:origin]
        h, w = times[t].hour, times[t].weekday()
        rows.append([y[t-24], y[t-48], y[t-168], day.mean(), day.min(), day.max(), week.mean(),
                     np.sin(h*np.pi/12), np.cos(h*np.pi/12), np.sin(w*2*np.pi/7), np.cos(w*2*np.pi/7)])
    return np.asarray(rows)


def fit_predict(x, y, stop, alpha):
    mean, scale = x[:stop].mean(axis=0), x[:stop].std(axis=0)
    design = np.c_[np.ones(len(x)), (x - mean) / np.where(scale > 0, scale, 1)]
    penalty = np.eye(design.shape[1]) * alpha
    penalty[0, 0] = 0
    weights = np.linalg.solve(design[:stop].T @ design[:stop] + penalty, design[:stop].T @ y[:stop])
    return design @ weights


def interval(values):
    values = np.asarray(values)
    rng = np.random.default_rng(20261026)
    means = []
    for _ in range(1000):
        starts = rng.integers(0, len(values), size=(len(values)+6)//7)
        sample = np.concatenate([values[(start + np.arange(7)) % len(values)] for start in starts])[:len(values)]
        means.append(sample.mean())
    return [round(float(v), 6) for v in np.quantile(means, [.025, .975])]


def replay(times, predictions, start):
    template = validate_sessions_csv((ROOT / "data/demo/prepared/sessions.csv").read_bytes())
    config = StationConfig.model_validate_json((ROOT / "data/demo/prepared/station.json").read_text())
    base = min(s.arrival_time for s in template).replace(hour=0)
    costs, outcomes = {"energy_only": {}, "with_demand": {}}, []
    for origin in range(start, len(times), 24):
        day = times[origin].to_pydatetime()
        sessions = [s.model_copy(update={"arrival_time": s.arrival_time + (day-base), "departure_time": s.departure_time + (day-base)}) for s in template]
        grids = {name: [PricePoint(timestamp=day+timedelta(minutes=15*i), price_eur_per_kwh=float(values[origin+i//4])) for i in range(96)] for name, values in predictions.items()}
        for mode, rate in (("energy_only", 0), ("with_demand", 15.2)):
            station = config.model_copy(deep=True)
            station.demand_tariff.eur_per_kw = rate
            for name, prices in grids.items():
                plan = optimize_schedule(sessions, station, prices)
                actual = compute_metrics(sessions, plan.allocations, station, grids["oracle"])
                costs[mode].setdefault(name, []).append(actual.cost_eur)
                if not plan.cost_optimal or actual.unserved_kwh > 1e-5 or not plan.validated:
                    outcomes.append({"day": str(day.date()), "mode": mode, "model": name, "status": plan.solver_status, "unserved_kwh": actual.unserved_kwh})
        print(f"Checked {day.date()}", flush=True)
    summary = {}
    for mode, models in costs.items():
        summary[mode] = {name: {"mean_realized_cost_eur": round(float(np.mean(values)), 6),
            "mean_oracle_regret_eur": round(float(np.mean(np.asarray(values)-models["oracle"])), 6)} for name, values in models.items()}
        for name in models.keys() - {"yesterday", "oracle"}:
            delta = np.asarray(models[name]) - models["yesterday"]
            summary[mode][f"{name}_minus_yesterday"] = {"mean_eur": round(float(delta.mean()), 6), "block_bootstrap_95_ci_eur": interval(delta)}
    return summary, outcomes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, help="Optional predictions from foundation_forecast.py")
    args = parser.parse_args()
    path = ROOT / "data/external/required/2019-04-01_2019-10-01/germany_day_ahead_eur_mwh_hourly.csv"
    frame = pd.read_csv(path)
    times = pd.to_datetime(frame.timestamp, utc=True)
    assert len(times) % 24 == 0 and times.iloc[0].hour == 0
    assert (times.diff().dropna() == pd.Timedelta(hours=1)).all()
    y = frame.price_eur_per_mwh.to_numpy(dtype=float) / 1000
    assert np.isfinite(y).all()
    days = len(y)//24
    train, test = int(days*.6)*24, int(days*.8)*24
    x, target = features(y, times), y[168:]
    scores = {a: float(np.abs(fit_predict(x, target, train-168, a)[train-168:test-168] - target[train-168:test-168]).mean()) for a in (.1, 1, 10, 100)}
    alpha = min(scores, key=scores.get)
    ridge = np.r_[np.full(168, np.nan), fit_predict(x, target, test-168, alpha)]
    models = {"yesterday": np.r_[np.full(24, np.nan), y[:-24]], "last_week": np.r_[np.full(168, np.nan), y[:-168]], "ridge": ridge, "oracle": y}
    foundation, diagnostics = None, {}
    if args.predictions:
        foundation = json.loads(args.predictions.read_text(encoding="utf-8"))
        assert foundation["input_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
        assert foundation["protocol_sha256"] == hashlib.sha256((ROOT/"docs/foundation-forecasting.md").read_bytes()).hexdigest()
        assert foundation["context_hours"] == 512 and foundation["horizon_hours"] == 24
        assert pd.Timestamp(foundation["test_start"]) == times[test]
        for name, values in foundation["models"].items():
            point, low, high = [np.asarray(values[k], dtype=float) for k in ("point", "q10", "q90")]
            assert all(len(a) == len(y)-test and np.isfinite(a).all() for a in (point, low, high))
            assert np.all(low <= high)
            models[name] = np.r_[np.full(test, np.nan), point]
            losses = [np.maximum(q*(y[test:]-forecast), (q-1)*(y[test:]-forecast)).mean() for q, forecast in ((.1, low), (.5, point), (.9, high))]
            diagnostics[name] = {"native_80_interval_coverage": round(float(((low <= y[test:]) & (y[test:] <= high)).mean()), 6),
                "mean_interval_width_eur_per_kwh": round(float((high-low).mean()), 8), "mean_pinball_loss_eur_per_kwh": round(float(np.mean(losses)), 8)}
    errors = {name: round(float(np.abs(pred[test:]-y[test:]).mean()), 8) for name, pred in models.items() if name != "oracle"}
    costs, incomplete = replay(times, models, test)
    result = {"data_source": "Bundesnetzagentur | SMARD.de, DE, native hourly 2019 observations", "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "protocol_sha256": hashlib.sha256((ROOT/"docs/forecasting.md").read_bytes()).hexdigest(), "train_end_exclusive": times[train].isoformat(), "test_start": times[test].isoformat(), "test_end_inclusive": times.iloc[-1].isoformat(),
        "test_days": (len(y)-test)//24, "issue_time": "00:00 UTC, using only earlier delivered-hour prices", "selected_ridge_alpha": alpha,
        "price_mae_eur_per_kwh": errors, "charging": costs, "incomplete_runs": incomplete,
        "scope": "Exploratory unpublished-price-gap stress test with a synthetic four-van roster; known day-ahead prices should not be forecast instead.", "foundation_models_run": bool(foundation and foundation["models"])}
    if foundation:
        result["foundation_metadata"] = {k: v for k, v in foundation.items() if k != "models"}
        result["foundation_models"] = {name: {k: v for k, v in model.items() if k not in {"point", "q10", "q90"}} for name, model in foundation["models"].items()}
        result["interval_diagnostics"] = diagnostics
    output = ROOT/("docs/foundation-forecast-results.json" if foundation else "docs/forecast-results.json")
    output.write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
