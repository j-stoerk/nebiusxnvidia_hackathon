"""Paired ORACLE replay and separate conformal holdout report, never an MPC claim."""

import argparse
from collections import defaultdict
import csv
from datetime import datetime, time, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.models import Price, Session, Station
from backend.app.services.analytics import metrics
from backend.app.services.csv_validator import horizon
from backend.app.services.evaluation import ConformalNeeds, chronological_split, coverage, paired_bootstrap
from backend.app.services.planning import solve_checked
from backend.app.services.scenario import Scenario, battery_energy
from backend.app.services.schedule_validator import validate_schedule
from backend.app.services.scheduler import baseline


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_csv(path, model):
    if path.stat().st_size > 32 * 1024 * 1024:
        raise ValueError("Evaluation input exceeds the 32 MiB budget")
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return [model.model_validate({k: v for k, v in row.items() if v != ""}) for row in csv.DictReader(stream)]


def paired_replay(sessions, station, prices, seconds):
    rows = []
    ledgers = {name: dict(station.demand_tariff.prior_peaks_kw) for name in ("FCFS", "EDF", "LLF", "OR-Tools")}
    histories = {name: [] for name in ledgers}
    day = datetime.combine(min(s.arrival_time for s in sessions).date(), time(), timezone.utc)
    last = max(s.departure_time for s in sessions)
    while day < last:
        end = day + timedelta(days=1)
        cohort = [s for s in sessions if s.arrival_time < end and s.departure_time > day]
        for name in ledgers:
            if not cohort:
                rows.append({"day": str(day.date()), "policy": name, "unserved_kwh": 0, "delivered_kwh": 0,
                             "peak_power_kw": 0, "cost_eur": 0, "energy_cost_eur": 0, "demand_cost_eur": 0,
                             "solver_status": "NO_SESSIONS", "shortfall_optimal": True, "cost_optimal": True})
                histories[name] = []
                continue
            start, finish = horizon(cohort, 15)
            selected = [p for p in prices if min(start, day) <= p.timestamp < max(finish, end)]
            config = station.model_copy(deep=True)
            config.demand_tariff.prior_peaks_kw = dict(ledgers[name])
            scenario = Scenario("evaluation", cohort, config, selected, max_horizon_days=7)
            scenario.now = max(day, start)
            ids = {s.vehicle_id for s in cohort}
            scenario.history = [r for r in histories[name] if r.vehicle_id in ids]
            result = solve_checked(scenario, seconds=seconds) if name == "OR-Tools" else baseline(scenario, name)
            validate_schedule(scenario, result)
            executed = [r.model_copy(update={"end_time": min(r.end_time, end)}) for r in result.allocations
                        if scenario.now <= r.start_time < end]
            totals = defaultdict(float)
            for record in [*scenario.history, *executed]:
                totals[record.vehicle_id] += battery_energy(record)
            unserved = sum(max(0, s.energy_required_kwh - totals[s.vehicle_id]) for s in cohort if s.departure_time <= end)
            histories[name] = [*scenario.history, *executed]
            # Daily metering includes only today's executed dispatch, never tomorrow's plan.
            scenario.start, scenario.end = day, end
            result.allocations = executed
            measured = metrics(scenario, result)
            ledgers[name].update(measured["billing_peaks_kw"])
            ledgers[name] = dict(sorted(ledgers[name].items())[-3:])
            rows.append({"day": str(day.date()), "policy": name, "unserved_kwh": unserved,
                         "delivered_kwh": measured["delivered_kwh"], "peak_power_kw": measured["peak_power_kw"],
                         "cost_eur": measured["cost_eur"], "energy_cost_eur": measured["energy_cost_eur"],
                         "demand_cost_eur": measured["demand_cost_eur"], "solver_status": result.solver_status,
                         "shortfall_optimal": result.shortfall_optimal, "cost_optimal": result.cost_optimal})
        day = end
    return rows


def comparisons(rows):
    by_day = defaultdict(dict)
    for row in rows:
        by_day[row["day"]][row["policy"]] = row
    # Include non-operating calendar days so a seven-day block means seven days.
    from datetime import date
    start, end = date.fromisoformat(min(by_day)), date.fromisoformat(max(by_day))
    calendar = [str(start + timedelta(days=i)) for i in range((end - start).days + 1)]
    reports = {}
    for policy in ("FCFS", "EDF", "LLF"):
        differences = {key: [] for key in ("unserved_kwh", "peak_power_kw", "cost_eur", "demand_cost_eur")}
        delivered_delta = 0
        for day in calendar:
            if day not in by_day:
                for values in differences.values():
                    values.append(0)
                continue
            a, b = by_day[day]["OR-Tools"], by_day[day][policy]
            delivered_delta += a["delivered_kwh"] - b["delivered_kwh"]
            for key, values in differences.items():
                values.append(a[key] - b[key])
        reports[policy] = {key: paired_bootstrap(values) for key, values in differences.items()}
        equal = abs(delivered_delta) <= 1e-4
        reports[policy]["equal_total_delivered_energy"] = equal
        reports[policy]["cost_comparison_valid"] = equal
        reports[policy]["h1_supported"] = reports[policy]["unserved_kwh"]["ci95"][1] <= 1e-5
        reports[policy]["h2_supported"] = all(reports[policy][key]["ci95"][1] < 0 for key in ("peak_power_kw", "demand_cost_eur"))
        reports[policy]["h3_supported"] = equal and reports[policy]["cost_eur"]["ci95"][1] < 0
    return reports


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sessions", type=Path, required=True)
    parser.add_argument("--prices", type=Path, required=True)
    parser.add_argument("--station", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / ".cache/evaluation/report.json")
    parser.add_argument("--solver-seconds", type=float, default=8)
    parser.add_argument("--context", type=Path, help="JSON describing tariff/equipment provenance and scenario assumptions")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Choose a fresh output path; evidence reports are not overwritten")
    if not .1 <= args.solver_seconds <= 60:
        parser.error("Solver budget must be 0.1–60 seconds per solve")
    metadata_path = args.sessions.with_suffix(".metadata.json")
    if not metadata_path.is_file():
        parser.error("Real-data provenance metadata is required beside the sessions CSV")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("sha256") != digest(args.sessions):
        parser.error("Session checksum differs from acquisition metadata")
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip():
        parser.error("Commit code and the evaluation protocol before running the held-out experiment")
    inputs = {name: digest(path) for name, path in {"sessions": args.sessions, "prices": args.prices,
              "station": args.station, "protocol": ROOT / "docs/evaluation.md", "provenance": metadata_path}.items()}
    if args.context:
        inputs["context"] = digest(args.context)
    sessions = load_csv(args.sessions, Session)
    if not sessions or max(s.arrival_time for s in sessions) - min(s.arrival_time for s in sessions) < timedelta(days=90):
        parser.error("Use months of real sessions (at least 90 days of arrival coverage; six months preferred)")
    if len({s.vehicle_id for s in sessions}) != len(sessions):
        parser.error("Session IDs must be unique; split repeated vehicle visits into session IDs")
    train, calibration, test = chronological_split(sessions)
    report = {"status": "running", "information": "Daily rolling oracle with actual labels and arrivals through day-end; overnight history preserved; not causal MPC",
              "context": json.loads(args.context.read_text(encoding="utf-8")) if args.context else {"scope": "User-provided scenario; equipment and tariff provenance must be verified"},
              "git_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "sha256": inputs, "provenance": metadata, "solver_seconds": args.solver_seconds,
              "split_sessions": {"train": len(train), "calibration": len(calibration), "test": len(test),
                                 "excluded_cross_boundary_labels": len(sessions) - len(train) - len(calibration) - len(test)}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    try:
        model = ConformalNeeds.fit(train, calibration)
        report["prediction"] = coverage(model, test)
        station = Station.model_validate_json(args.station.read_text(encoding="utf-8"))
        cutoff = (min(s.arrival_time for s in test) + timedelta(days=1)).date()
        replay = paired_replay(sessions, station, load_csv(args.prices, Price), args.solver_seconds)
        report["test_calendar_start"] = str(cutoff)
        report["days"] = [r for r in replay if r["day"] >= str(cutoff)]
        report["paired_optimizer_minus_reference"] = comparisons(report["days"])
        report["status"] = "complete_oracle_benchmark"
    except (ValueError, RuntimeError) as exc:
        report["status"], report["error"] = "incomplete_no_claims", str(exc)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"{report['status']}: {args.output}")
    if report["status"] == "incomplete_no_claims":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
