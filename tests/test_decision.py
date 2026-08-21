"""Unit tests for the pure decision function. No Home Assistant needed."""

from datetime import time

import pytest

from custom_components.glorp_battery_optimization.const import (
    AC_MODE_INPUT,
    AC_MODE_OUTPUT,
    REASON_ENTITY_UNAVAILABLE,
    REASON_IDLE,
    REASON_MASTER_DISABLED,
    REASON_NIGHT_CHARGE,
    REASON_SOC_MAX_PROTECT,
    REASON_SOC_MIN_PROTECT,
    REASON_SOLAR_SURPLUS,
    REASON_SUBSCRIPTION_LIMIT,
    REASON_ZERO_EXPORT,
)
from custom_components.glorp_battery_optimization.decision import decide

BASE_SETTINGS = {
    "soc_min": 10,
    "soc_max": 95,
    "night_charge_soc_threshold": 50,
    "night_charge_power": 500,
    "off_peak_start": time(22, 30),
    "off_peak_end": time(6, 30),
    "max_charge_w": 1600,
    "max_discharge_w": 1600,
    "max_grid_import_w": 5500,  # e.g. a 6 kVA subscription minus a 500 W margin
    "master_enable": True,
    "enable_night_charge": True,
    "enable_solar_charge": True,
    "enable_zero_export": True,
}


def _inputs(soc, grid_power_w, now_time):
    return {"soc": soc, "grid_power_w": grid_power_w, "now_time": now_time}


def test_master_disabled_is_hands_off():
    result = decide(_inputs(50, 500, time(12, 0)), {**BASE_SETTINGS, "master_enable": False})
    assert result["active"] is False
    assert result["reason"] == REASON_MASTER_DISABLED


@pytest.mark.parametrize("soc,grid", [(None, 100), (50, None)])
def test_missing_inputs_is_hands_off(soc, grid):
    result = decide(_inputs(soc, grid, time(12, 0)), BASE_SETTINGS)
    assert result["active"] is False
    assert result["reason"] == REASON_ENTITY_UNAVAILABLE


def test_zero_export_discharges_to_match_grid_import():
    result = decide(_inputs(50, 700, time(12, 0)), BASE_SETTINGS)
    assert result == {"active": True, "mode": AC_MODE_OUTPUT, "power_w": 700, "reason": REASON_ZERO_EXPORT}


def test_zero_export_is_capped_at_max_discharge():
    result = decide(_inputs(50, 5000, time(12, 0)), BASE_SETTINGS)
    assert result["power_w"] == BASE_SETTINGS["max_discharge_w"]


def test_solar_surplus_charges_to_match_export():
    result = decide(_inputs(50, -400, time(12, 0)), BASE_SETTINGS)
    assert result == {"active": True, "mode": AC_MODE_INPUT, "power_w": 400, "reason": REASON_SOLAR_SURPLUS}


def test_night_charge_takes_priority_over_solar_surplus():
    # Off-peak window, low SOC, and export happening at the same time.
    result = decide(_inputs(30, -400, time(23, 0)), BASE_SETTINGS)
    assert result["reason"] == REASON_NIGHT_CHARGE
    assert result["power_w"] == BASE_SETTINGS["night_charge_power"]


def test_night_charge_window_wraps_past_midnight():
    result = decide(_inputs(30, 0, time(2, 0)), BASE_SETTINGS)
    assert result["reason"] == REASON_NIGHT_CHARGE


def test_night_charge_does_not_fire_above_its_own_threshold():
    result = decide(_inputs(80, 0, time(23, 0)), BASE_SETTINGS)
    assert result["reason"] == REASON_IDLE


def test_soc_min_blocks_discharge_but_not_charging():
    # At soc_min exactly, discharge must not fire...
    result = decide(_inputs(10, 700, time(12, 0)), BASE_SETTINGS)
    assert result == {"active": True, "mode": None, "power_w": 0, "reason": REASON_SOC_MIN_PROTECT}
    # ...but charging from solar surplus still works at the same SOC.
    result = decide(_inputs(10, -400, time(12, 0)), BASE_SETTINGS)
    assert result["mode"] == AC_MODE_INPUT


def test_soc_max_blocks_charging_but_not_discharge():
    result = decide(_inputs(95, -400, time(12, 0)), BASE_SETTINGS)
    assert result == {"active": True, "mode": None, "power_w": 0, "reason": REASON_SOC_MAX_PROTECT}
    result = decide(_inputs(95, 700, time(12, 0)), BASE_SETTINGS)
    assert result["mode"] == AC_MODE_OUTPUT


def test_idle_when_grid_power_is_zero():
    result = decide(_inputs(50, 0, time(12, 0)), BASE_SETTINGS)
    assert result == {"active": True, "mode": None, "power_w": 0, "reason": REASON_IDLE}


def test_disabled_strategy_is_skipped():
    settings = {**BASE_SETTINGS, "enable_zero_export": False}
    result = decide(_inputs(50, 700, time(12, 0)), settings)
    assert result["reason"] == REASON_IDLE


def test_night_charge_is_capped_by_subscription_headroom():
    # House already drawing 5300 W; only 200 W of headroom left under the
    # 5500 W limit, well below the configured 500 W night charge power.
    settings = {**BASE_SETTINGS, "enable_zero_export": False}
    result = decide(_inputs(30, 5300, time(23, 0)), settings)
    assert result == {"active": True, "mode": AC_MODE_INPUT, "power_w": 200, "reason": REASON_NIGHT_CHARGE}


def test_night_charge_blocked_when_subscription_already_exceeded():
    settings = {**BASE_SETTINGS, "enable_zero_export": False}
    result = decide(_inputs(30, 5500, time(23, 0)), settings)
    assert result == {"active": True, "mode": None, "power_w": 0, "reason": REASON_SUBSCRIPTION_LIMIT}


def test_night_charge_blocked_falls_through_to_zero_export():
    # zero_export stays enabled here: if night charge can't fit, discharging
    # to relieve the same overload is a sensible fallback, not a conflict.
    result = decide(_inputs(30, 5500, time(23, 0)), BASE_SETTINGS)
    assert result["reason"] == REASON_ZERO_EXPORT
    assert result["mode"] == AC_MODE_OUTPUT
