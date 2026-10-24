"""Two-stage CC/CV envelope. Dispatch is constant power within each interval.

After transition SoC, the acceptance ceiling falls linearly with stored energy.
Enforcing it at the interval END is conservative and valid throughout the slot;
it is not a claim of calibrated chemistry or an exact exponential CV trajectory.
Missing SoC/capacity means constant-power mode, never invented telemetry.
"""

import math


def taper_ceiling(session, delivered_kwh):
    if session.battery_capacity_kwh is None:
        return session.max_charging_power_kw
    capacity = session.battery_capacity_kwh
    headroom = capacity * (1 - session.initial_soc) - delivered_kwh
    return min(session.max_charging_power_kw,
               session.max_charging_power_kw * max(0, headroom) / (capacity * (1 - session.transition_soc)))


def sustainable_power(session, delivered_kwh, duration_hours, efficiency):
    """Closed-form largest constant setpoint satisfying the terminal CV ceiling."""
    if session.battery_capacity_kwh is None:
        return session.max_charging_power_kw
    capacity, rate = session.battery_capacity_kwh, session.max_charging_power_kw
    headroom = capacity * (1 - session.initial_soc) - delivered_kwh
    return max(0, min(rate, rate * headroom / (capacity * (1 - session.transition_soc) + rate * duration_hours * efficiency)))


def minimum_hours(session, delivered_kwh, remaining_kwh, rate, efficiency):
    """Continuous CC/CV fastest-charge lower bound for LLF priority."""
    if remaining_kwh <= 0:
        return 0
    if rate <= 0:
        return math.inf
    if session.battery_capacity_kwh is None:
        return remaining_kwh / (rate * efficiency)
    capacity, maximum = session.battery_capacity_kwh, session.max_charging_power_kw
    headroom = capacity * (1 - session.initial_soc) - delivered_kwh
    scale = capacity * (1 - session.transition_soc)
    flat = min(remaining_kwh, max(0, headroom - scale * rate / maximum))
    if remaining_kwh - flat <= 1e-10:
        return flat / (rate * efficiency)
    if headroom - remaining_kwh <= 0:
        return math.inf  # This ideal CV curve approaches full SoC asymptotically.
    return flat / (rate * efficiency) + scale / (maximum * efficiency) * math.log((headroom - flat) / (headroom - remaining_kwh))
