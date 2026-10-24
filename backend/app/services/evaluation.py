"""Chronological, paired evaluation primitives. No test labels enter calibration."""

from dataclasses import dataclass
from datetime import timedelta
import math
import random
from statistics import mean, median

from .scenario import hours


def chronological_split(sessions):
    ordered = sorted(sessions, key=lambda s: s.arrival_time)
    start, span = ordered[0].arrival_time, ordered[-1].arrival_time - ordered[0].arrival_time
    calibration_start, test_start = start + span / 2, start + span * .75
    # Complete labels must be available before the next block begins.
    train = [s for s in ordered if s.departure_time < calibration_start]
    calibration = [s for s in ordered if s.arrival_time >= calibration_start and s.departure_time < test_start]
    test = [s for s in ordered if s.arrival_time >= test_start]
    if not train or not calibration or not test:
        raise ValueError("Need nonempty, disjoint train/calibration/test time blocks")
    return train, calibration, test


def conformal_quantile(scores, alpha):
    if not 0 < alpha < 1 or not scores or any(not math.isfinite(s) for s in scores):
        raise ValueError("Finite calibration scores and alpha in (0,1) required")
    rank = math.ceil((len(scores) + 1) * (1 - alpha))
    if rank > len(scores):
        raise ValueError("Insufficient calibration data for a finite coverage bound at this alpha")
    return sorted(scores)[rank - 1]


@dataclass
class ConformalNeeds:
    """Training-only weekday/hour medians; two one-sided Bonferroni bounds.

    Theoretical joint marginal coverage needs exchangeability. This module does
    not turn temporal data into exchangeable samples or certify fleet readiness.
    """
    centers: dict
    fallback: tuple
    departure_margin: float
    energy_margin: float
    alpha: float
    departure_radius: float = 0
    energy_radius: float = 0

    @staticmethod
    def key(session):
        return session.arrival_time.weekday(), session.arrival_time.hour // 4

    @classmethod
    def fit(cls, train, calibration, alpha=.05):
        if not train or not calibration or max(s.departure_time for s in train) >= min(s.arrival_time for s in calibration):
            raise ValueError("Training labels must precede calibration arrivals")
        center = lambda rows: (median(hours(s.arrival_time, s.departure_time) for s in rows), median(s.energy_required_kwh for s in rows))
        groups = {}
        for session in train:
            groups.setdefault(cls.key(session), []).append(session)
        model = cls({k: center(rows) for k, rows in groups.items() if len(rows) >= 10}, center(train), 0, 0, alpha)
        departure_scores, energy_scores = [], []
        for session in calibration:
            duration, energy = model.point(session)
            departure_scores.append(duration - hours(session.arrival_time, session.departure_time))
            energy_scores.append(session.energy_required_kwh - energy)
        model.departure_margin = conformal_quantile(departure_scores, alpha / 2)
        model.energy_margin = conformal_quantile(energy_scores, alpha / 2)
        model.departure_radius = conformal_quantile([abs(s) for s in departure_scores], alpha / 2)
        model.energy_radius = conformal_quantile([abs(s) for s in energy_scores], alpha / 2)
        return model

    def point(self, session):
        return self.centers.get(self.key(session), self.fallback)

    def bounds(self, session):
        duration, energy = self.point(session)
        return {"departure_lower": session.arrival_time + timedelta(hours=max(0, duration - self.departure_margin)),
                "energy_upper_kwh": max(0, energy + self.energy_margin)}


def pinball(actual, prediction, quantile):
    error = actual - prediction
    return max(quantile * error, (quantile - 1) * error)


def coverage(model, test):
    if not test:
        raise ValueError("Empty holdout")
    records, intervals = [], []
    for session in test:
        bound = model.bounds(session)
        lower = hours(session.arrival_time, bound["departure_lower"])
        actual = hours(session.arrival_time, session.departure_time)
        duration, energy = model.point(session)
        d_lower, d_upper = max(0, duration - model.departure_radius), duration + model.departure_radius
        e_lower, e_upper = max(0, energy - model.energy_radius), energy + model.energy_radius
        intervals.append((d_lower <= actual <= d_upper, e_lower <= session.energy_required_kwh <= e_upper,
                          d_upper - d_lower, e_upper - e_lower))
        records.append((actual >= lower, session.energy_required_kwh <= bound["energy_upper_kwh"],
                        pinball(actual, lower, model.alpha / 2),
                        pinball(session.energy_required_kwh, bound["energy_upper_kwh"], 1 - model.alpha / 2)))
    return {"sessions": len(records), "departure_lower_coverage": mean(r[0] for r in records),
            "energy_upper_coverage": mean(r[1] for r in records), "joint_coverage": mean(r[0] and r[1] for r in records),
            "departure_pinball_hours": mean(r[2] for r in records), "energy_pinball_kwh": mean(r[3] for r in records),
            "nominal_joint_coverage": 1 - model.alpha,
            "joint_two_sided_interval_coverage": mean(r[0] and r[1] for r in intervals),
            "mean_departure_interval_width_hours": mean(r[2] for r in intervals),
            "mean_energy_interval_width_kwh": mean(r[3] for r in intervals),
            "scope": "One-sided interval coverage, not executed readiness or a time-series coverage guarantee."}


def paired_bootstrap(differences, seed=20261024, repetitions=2000, block_days=7):
    """Paired moving-block bootstrap of mean daily differences; preserve order."""
    if block_days < 1 or repetitions < 2:
        raise ValueError("Positive block length and at least two resamples required")
    if len(differences) < 2 * block_days or not all(math.isfinite(v) for v in differences):
        raise ValueError("Need at least two complete finite seven-day blocks")
    rng, means = random.Random(seed), []
    for _ in range(repetitions):
        sample = []
        while len(sample) < len(differences):
            start = rng.randrange(len(differences) - block_days + 1)
            sample.extend(differences[start:start + block_days])
        means.append(mean(sample[:len(differences)]))
    means.sort()
    return {"mean": mean(differences), "ci95": [means[int(.025 * repetitions)], means[min(repetitions - 1, math.ceil(.975 * repetitions) - 1)]],
            "days": len(differences), "block_days": block_days, "replicates": repetitions, "seed": seed}
