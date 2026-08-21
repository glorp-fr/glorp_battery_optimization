"""Runtime glue: listens for grid power changes, runs the decision function,
and writes the result to the zendure_ha device entities."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import dt as dt_util

from .const import (
    AC_MODE_INPUT,
    CONF_AC_MODE_ENTITY,
    CONF_GRID_POWER_ENTITY,
    CONF_INPUT_LIMIT_ENTITY,
    CONF_MAX_CHARGE_W,
    CONF_MAX_DISCHARGE_W,
    CONF_OUTPUT_LIMIT_ENTITY,
    CONF_SOC_ENTITY,
    DEFAULT_DEADBAND_W,
    DEFAULT_NIGHT_CHARGE_POWER,
    DEFAULT_NIGHT_CHARGE_SOC_THRESHOLD,
    DEFAULT_OFF_PEAK_END,
    DEFAULT_OFF_PEAK_START,
    DEFAULT_SOC_MAX,
    DEFAULT_SOC_MIN,
    SETTING_DEADBAND_W,
    SETTING_ENABLE_NIGHT_CHARGE,
    SETTING_ENABLE_SOLAR_CHARGE,
    SETTING_ENABLE_ZERO_EXPORT,
    SETTING_MASTER_ENABLE,
    SETTING_NIGHT_CHARGE_POWER,
    SETTING_NIGHT_CHARGE_SOC_THRESHOLD,
    SETTING_OFF_PEAK_END,
    SETTING_OFF_PEAK_START,
    SETTING_SOC_MAX,
    SETTING_SOC_MIN,
)
from .decision import Decision, decide

_LOGGER = logging.getLogger(__name__)


def _parse_hhmmss(value: str):
    return datetime.strptime(value, "%H:%M:%S").time()


class ZendureOptimizationController:
    """Owns the live settings, runs decide() on grid changes, writes commands."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.last_decision: Decision | None = None
        self._last_written: dict[str, Any] | None = None
        self._unsub = None
        # Grid power can change faster than a full write (mode + 2 numbers,
        # each a real round-trip to the device) completes. Without this lock,
        # overlapping cycles interleave their service calls and the device
        # ends up with a mode from one decision and a limit from another.
        self._cycle_lock = asyncio.Lock()
        # Live-adjustable settings. Number/switch entities update these
        # directly (see number.py / switch.py) so a cycle always reads the
        # current value without going through hass.states for our own entities.
        self.settings: dict[str, Any] = {
            SETTING_SOC_MIN: DEFAULT_SOC_MIN,
            SETTING_SOC_MAX: DEFAULT_SOC_MAX,
            SETTING_NIGHT_CHARGE_SOC_THRESHOLD: DEFAULT_NIGHT_CHARGE_SOC_THRESHOLD,
            SETTING_NIGHT_CHARGE_POWER: DEFAULT_NIGHT_CHARGE_POWER,
            SETTING_OFF_PEAK_START: _parse_hhmmss(DEFAULT_OFF_PEAK_START),
            SETTING_OFF_PEAK_END: _parse_hhmmss(DEFAULT_OFF_PEAK_END),
            SETTING_DEADBAND_W: DEFAULT_DEADBAND_W,
            SETTING_ENABLE_NIGHT_CHARGE: True,
            SETTING_ENABLE_SOLAR_CHARGE: True,
            SETTING_ENABLE_ZERO_EXPORT: True,
            SETTING_MASTER_ENABLE: True,
            "max_charge_w": entry.data[CONF_MAX_CHARGE_W],
            "max_discharge_w": entry.data[CONF_MAX_DISCHARGE_W],
        }
        # Sensor entities register a callback here to refresh after a cycle.
        self._sensor_update_callbacks: list = []

    async def async_start(self) -> None:
        grid_entity = self.entry.data[CONF_GRID_POWER_ENTITY]
        self._unsub = async_track_state_change_event(self.hass, [grid_entity], self._async_on_grid_change)

    def async_stop(self) -> None:
        if self._unsub:
            self._unsub()
            self._unsub = None

    def register_sensor_callback(self, cb) -> None:
        self._sensor_update_callbacks.append(cb)

    @callback
    def _async_on_grid_change(self, event: Event[EventStateChangedData]) -> None:
        self.hass.async_create_task(self.async_run_cycle())

    def _read_float(self, entity_id: str) -> float | None:
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable"):
            return None
        try:
            return float(state.state)
        except ValueError:
            return None

    async def async_run_cycle(self) -> None:
        async with self._cycle_lock:
            soc = self._read_float(self.entry.data[CONF_SOC_ENTITY])
            grid_power_w = self._read_float(self.entry.data[CONF_GRID_POWER_ENTITY])
            now_time = dt_util.now().time()

            result = decide(
                {"soc": soc, "grid_power_w": grid_power_w, "now_time": now_time},
                self.settings,
            )
            self.last_decision = result

            for cb in self._sensor_update_callbacks:
                cb()

            if not result["active"]:
                return

            await self._async_write_if_changed(result)

    async def _async_write_if_changed(self, result: Decision) -> None:
        previous = self._last_written
        if previous is not None:
            same_mode = previous["mode"] == result["mode"]
            within_deadband = abs(previous["power_w"] - result["power_w"]) < self.settings[SETTING_DEADBAND_W]
            if same_mode and within_deadband:
                return

        ac_mode_entity = self.entry.data[CONF_AC_MODE_ENTITY]
        input_limit_entity = self.entry.data[CONF_INPUT_LIMIT_ENTITY]
        output_limit_entity = self.entry.data[CONF_OUTPUT_LIMIT_ENTITY]

        if result["mode"] == AC_MODE_INPUT:
            await self.hass.services.async_call(
                "select", "select_option", {"entity_id": ac_mode_entity, "option": AC_MODE_INPUT}, blocking=True
            )
            await self.hass.services.async_call(
                "number", "set_value", {"entity_id": output_limit_entity, "value": 0}, blocking=True
            )
            await self.hass.services.async_call(
                "number", "set_value", {"entity_id": input_limit_entity, "value": result["power_w"]}, blocking=True
            )
        elif result["mode"] is not None:  # output / discharge
            await self.hass.services.async_call(
                "select", "select_option", {"entity_id": ac_mode_entity, "option": result["mode"]}, blocking=True
            )
            await self.hass.services.async_call(
                "number", "set_value", {"entity_id": input_limit_entity, "value": 0}, blocking=True
            )
            await self.hass.services.async_call(
                "number", "set_value", {"entity_id": output_limit_entity, "value": result["power_w"]}, blocking=True
            )
        else:  # stop
            await self.hass.services.async_call(
                "number", "set_value", {"entity_id": input_limit_entity, "value": 0}, blocking=True
            )
            await self.hass.services.async_call(
                "number", "set_value", {"entity_id": output_limit_entity, "value": 0}, blocking=True
            )

        self._last_written = {"mode": result["mode"], "power_w": result["power_w"]}
