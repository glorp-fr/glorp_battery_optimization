"""Pure decision logic for Zendure battery optimization.

Deliberately framework-free: no Home Assistant imports, no I/O, no internal
state. Given the same inputs and settings it always returns the same
decision, which makes it testable with plain pytest and auditable without
running Home Assistant.
"""

from __future__ import annotations

from datetime import time
from typing import Any, TypedDict

from .const import (
    AC_MODE_INPUT,
    AC_MODE_OUTPUT,
    REASON_ENTITY_UNAVAILABLE,
    REASON_IDLE,
    REASON_MASTER_DISABLED,
    REASON_NIGHT_CHARGE,
    REASON_SOC_MAX_PROTECT,
    REASON_SOC_MIN_PROTECT,
    REASON_SOLAR_SURPLUS,
    REASON_ZERO_EXPORT,
)


class Decision(TypedDict):
    active: bool  # False means "hands off, do not write anything this cycle"
    mode: str | None  # AC_MODE_INPUT, AC_MODE_OUTPUT, or None when stopped
    power_w: int
    reason: str


def _in_off_peak_window(now: time, start: time, end: time) -> bool:
    """Return whether `now` falls in the [start, end) window, handling overnight wrap."""
    if start <= end:
        return start <= now < end
    return now >= start or now < end


def decide(inputs: dict[str, Any], settings: dict[str, Any]) -> Decision:
    """Compute the desired charge/discharge command for this cycle.

    `inputs` carries live readings: soc (0-100 or None), grid_power_w
    (positive = importing from grid, negative = exporting, or None), and
    now_time (datetime.time).

    `settings` carries the current configuration (see const.py for keys):
    soc_min/soc_max, night charge window/threshold/power, max charge/
    discharge power, and the per-strategy enable switches.
    """
    if not settings["master_enable"]:
        return Decision(active=False, mode=None, power_w=0, reason=REASON_MASTER_DISABLED)

    soc = inputs.get("soc")
    grid_power_w = inputs.get("grid_power_w")
    now_time = inputs["now_time"]

    if soc is None or grid_power_w is None:
        return Decision(active=False, mode=None, power_w=0, reason=REASON_ENTITY_UNAVAILABLE)

    soc_min = settings["soc_min"]
    soc_max = settings["soc_max"]
    max_charge_w = settings["max_charge_w"]
    max_discharge_w = settings["max_discharge_w"]

    # SOC protection is directional, not a blanket override: a low SOC must
    # never block charging (that's how it recovers), and a high SOC must
    # never block discharging. Each strategy below is guarded only against
    # the direction it could hurt.

    if (
        settings["enable_night_charge"]
        and _in_off_peak_window(now_time, settings["off_peak_start"], settings["off_peak_end"])
        and soc < settings["night_charge_soc_threshold"]
        and soc < soc_max
    ):
        power = min(settings["night_charge_power"], max_charge_w)
        return Decision(active=True, mode=AC_MODE_INPUT, power_w=int(power), reason=REASON_NIGHT_CHARGE)

    if settings["enable_solar_charge"] and grid_power_w < 0 and soc < soc_max:
        power = min(-grid_power_w, max_charge_w)
        return Decision(active=True, mode=AC_MODE_INPUT, power_w=int(power), reason=REASON_SOLAR_SURPLUS)

    if settings["enable_zero_export"] and grid_power_w > 0 and soc > soc_min:
        power = min(grid_power_w, max_discharge_w)
        return Decision(active=True, mode=AC_MODE_OUTPUT, power_w=int(power), reason=REASON_ZERO_EXPORT)

    # Nothing applies: either genuinely idle, or a strategy would have fired
    # but the directional SOC guard blocked it. Command an explicit stop
    # either way, so the device never coasts on a stale setpoint.
    reason = REASON_IDLE
    if soc >= soc_max and grid_power_w < 0:
        reason = REASON_SOC_MAX_PROTECT
    elif soc <= soc_min and grid_power_w > 0:
        reason = REASON_SOC_MIN_PROTECT
    return Decision(active=True, mode=None, power_w=0, reason=reason)
