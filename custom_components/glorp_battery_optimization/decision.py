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
    REASON_HYSTERESIS_HOLD,
    REASON_IDLE,
    REASON_MASTER_DISABLED,
    REASON_NIGHT_CHARGE,
    REASON_SOC_MAX_PROTECT,
    REASON_SOC_MIN_PROTECT,
    REASON_SOLAR_SURPLUS,
    REASON_SUBSCRIPTION_LIMIT,
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
    (positive = importing from grid, negative = exporting, or None),
    now_time (datetime.time), and current_power_w (the battery power we
    ourselves last commanded: positive = discharging, negative = charging,
    0 = idle/unknown; defaults to 0).

    `settings` carries the current configuration (see const.py for keys):
    soc_min/soc_max, night charge window/threshold/power, max charge/
    discharge power, max_grid_import_w (the grid subscription limit minus
    its safety margin, in watts), mode_switch_hysteresis_w, and the
    per-strategy enable switches.
    """
    if not settings["master_enable"]:
        return Decision(active=False, mode=None, power_w=0, reason=REASON_MASTER_DISABLED)

    soc = inputs.get("soc")
    grid_power_w = inputs.get("grid_power_w")
    now_time = inputs["now_time"]
    current_power_w = inputs.get("current_power_w", 0)

    if soc is None or grid_power_w is None:
        return Decision(active=False, mode=None, power_w=0, reason=REASON_ENTITY_UNAVAILABLE)

    soc_min = settings["soc_min"]
    soc_max = settings["soc_max"]
    max_charge_w = settings["max_charge_w"]
    max_discharge_w = settings["max_discharge_w"]
    hysteresis_w = settings["mode_switch_hysteresis_w"]

    # grid_power_w already nets out whatever the battery is currently doing
    # (it's measured downstream of it), so it's only the residual left
    # uncovered, not the whole load. Add back our own last commanded power to
    # recover what the grid would read with the battery idle — the actual
    # target for solar/zero-export. Without this, each cycle would net out
    # its own previous output and only ever chase half the load.
    residual_w = grid_power_w + current_power_w

    current_direction = None
    if current_power_w > 0:
        current_direction = AC_MODE_OUTPUT
    elif current_power_w < 0:
        current_direction = AC_MODE_INPUT

    # SOC protection is directional, not a blanket override: a low SOC must
    # never block charging (that's how it recovers), and a high SOC must
    # never block discharging. Each strategy below is guarded only against
    # the direction it could hurt.

    # Night charge is the only strategy that adds load regardless of what the
    # house is already drawing, so it's the only one that can trip the grid
    # subscription's breaker. Solar surplus and zero-export charging/discharge
    # only ever move the grid reading toward zero, never past the current
    # draw, so they need no such cap.
    night_charge_blocked_by_subscription = False
    if (
        settings["enable_night_charge"]
        and _in_off_peak_window(now_time, settings["off_peak_start"], settings["off_peak_end"])
        and soc < settings["night_charge_soc_threshold"]
        and soc < soc_max
    ):
        headroom_w = max(0.0, settings["max_grid_import_w"] - grid_power_w)
        power = min(settings["night_charge_power"], max_charge_w, headroom_w)
        if power > 0:
            return Decision(active=True, mode=AC_MODE_INPUT, power_w=int(power), reason=REASON_NIGHT_CHARGE)
        night_charge_blocked_by_subscription = True

    held_by_hysteresis = False

    if settings["enable_solar_charge"] and residual_w < 0 and soc < soc_max:
        # A brief dip that hasn't cleared the hysteresis band yet: hold the
        # current discharge direction (at 0 W) instead of flipping the AC
        # mode relay for what might reverse again a few seconds later.
        if current_direction == AC_MODE_OUTPUT and -residual_w <= hysteresis_w:
            held_by_hysteresis = True
        else:
            power = min(-residual_w, max_charge_w)
            return Decision(active=True, mode=AC_MODE_INPUT, power_w=int(power), reason=REASON_SOLAR_SURPLUS)

    if settings["enable_zero_export"] and residual_w > 0 and soc > soc_min:
        if current_direction == AC_MODE_INPUT and residual_w <= hysteresis_w:
            held_by_hysteresis = True
        else:
            power = min(residual_w, max_discharge_w)
            return Decision(active=True, mode=AC_MODE_OUTPUT, power_w=int(power), reason=REASON_ZERO_EXPORT)

    # Nothing applies: either genuinely idle, a strategy was blocked by the
    # directional SOC guard, or one was held back by hysteresis. Command an
    # explicit stop either way, so the device never coasts on a stale
    # setpoint — but keep the current direction (if any) so build_commands
    # re-affirms the same AC mode instead of touching the relay for nothing.
    reason = REASON_IDLE
    if night_charge_blocked_by_subscription:
        reason = REASON_SUBSCRIPTION_LIMIT
    elif soc >= soc_max and residual_w < 0:
        reason = REASON_SOC_MAX_PROTECT
    elif soc <= soc_min and residual_w > 0:
        reason = REASON_SOC_MIN_PROTECT
    elif held_by_hysteresis:
        reason = REASON_HYSTERESIS_HOLD
    return Decision(active=True, mode=current_direction, power_w=0, reason=reason)
