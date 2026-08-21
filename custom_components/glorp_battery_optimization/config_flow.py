"""Config flow for Glorp's Battery Optimization.

Only wires up the fixed setup: which entities to read/write, and the
device's own power/capacity limits. The live-adjustable thresholds (SOC
limits, night charge settings, per-strategy switches) are exposed as
regular number/switch/time entities instead, editable from any dashboard
without going through this flow again.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_AC_MODE_ENTITY,
    CONF_CAPACITY_KWH,
    CONF_GRID_POWER_ENTITY,
    CONF_INPUT_LIMIT_ENTITY,
    CONF_MAX_CHARGE_W,
    CONF_MAX_DISCHARGE_W,
    CONF_OUTPUT_LIMIT_ENTITY,
    CONF_SOC_ENTITY,
    DOMAIN,
)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_AC_MODE_ENTITY): selector.EntitySelector(selector.EntitySelectorConfig(domain="select")),
        vol.Required(CONF_INPUT_LIMIT_ENTITY): selector.EntitySelector(selector.EntitySelectorConfig(domain="number")),
        vol.Required(CONF_OUTPUT_LIMIT_ENTITY): selector.EntitySelector(selector.EntitySelectorConfig(domain="number")),
        vol.Required(CONF_SOC_ENTITY): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
        vol.Required(CONF_GRID_POWER_ENTITY): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
        vol.Required(CONF_MAX_CHARGE_W, default=1600): selector.NumberSelector(
            selector.NumberSelectorConfig(min=0, max=20000, step=50, unit_of_measurement="W")
        ),
        vol.Required(CONF_MAX_DISCHARGE_W, default=1600): selector.NumberSelector(
            selector.NumberSelectorConfig(min=0, max=20000, step=50, unit_of_measurement="W")
        ),
        vol.Required(CONF_CAPACITY_KWH, default=3.84): selector.NumberSelector(
            selector.NumberSelectorConfig(min=0, max=200, step=0.1, unit_of_measurement="kWh")
        ),
    }
)


class ZendureOptimizationConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Glorp's Battery Optimization."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="Glorp's Battery Optimization", data=user_input)
        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)
