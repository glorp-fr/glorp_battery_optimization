"""Config flow for Glorp's Battery Optimization.

Only wires up the fixed setup: how the battery is driven, which entities to
read/write, and the device's own power/capacity limits. The live-adjustable
thresholds (SOC limits, night charge settings, per-strategy switches) are
exposed as regular number/switch/time entities instead, editable from any
dashboard without going through this flow again.

Step order: pick the control mode first (`user`), then a second step shows
the entity selectors specific to that mode (`two_commands` or
`single_command`) alongside the fields common to both.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_AC_MODE_ENTITY,
    CONF_CAPACITY_KWH,
    CONF_CONTROL_MODE,
    CONF_GRID_POWER_ENTITY,
    CONF_INPUT_LIMIT_ENTITY,
    CONF_MAX_CHARGE_W,
    CONF_MAX_DISCHARGE_W,
    CONF_OUTPUT_LIMIT_ENTITY,
    CONF_POWER_ENTITY,
    CONF_POWER_SIGN,
    CONF_SOC_ENTITY,
    CONF_SUBSCRIPTION_KVA,
    CONTROL_MODE_SINGLE_COMMAND,
    CONTROL_MODE_TWO_COMMANDS,
    DOMAIN,
    POWER_SIGN_POSITIVE_CHARGE,
    POWER_SIGN_POSITIVE_DISCHARGE,
    SUBSCRIPTION_KVA_OPTIONS,
)

CONTROL_MODE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CONTROL_MODE, default=CONTROL_MODE_TWO_COMMANDS): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[CONTROL_MODE_TWO_COMMANDS, CONTROL_MODE_SINGLE_COMMAND],
                mode=selector.SelectSelectorMode.LIST,
                translation_key=CONF_CONTROL_MODE,
            )
        ),
    }
)

_COMMON_SCHEMA_FIELDS = {
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
    vol.Required(CONF_SUBSCRIPTION_KVA, default=str(SUBSCRIPTION_KVA_OPTIONS[1])): selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[str(kva) for kva in SUBSCRIPTION_KVA_OPTIONS],
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    ),
}

TWO_COMMANDS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_AC_MODE_ENTITY): selector.EntitySelector(selector.EntitySelectorConfig(domain="select")),
        vol.Required(CONF_INPUT_LIMIT_ENTITY): selector.EntitySelector(selector.EntitySelectorConfig(domain="number")),
        vol.Required(CONF_OUTPUT_LIMIT_ENTITY): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="number")
        ),
        **_COMMON_SCHEMA_FIELDS,
    }
)

SINGLE_COMMAND_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_POWER_ENTITY): selector.EntitySelector(selector.EntitySelectorConfig(domain="number")),
        vol.Required(CONF_POWER_SIGN, default=POWER_SIGN_POSITIVE_DISCHARGE): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[POWER_SIGN_POSITIVE_DISCHARGE, POWER_SIGN_POSITIVE_CHARGE],
                mode=selector.SelectSelectorMode.LIST,
                translation_key=CONF_POWER_SIGN,
            )
        ),
        **_COMMON_SCHEMA_FIELDS,
    }
)


class ZendureOptimizationConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Glorp's Battery Optimization."""

    VERSION = 1

    def __init__(self) -> None:
        self._control_mode: str | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._control_mode = user_input[CONF_CONTROL_MODE]
            if self._control_mode == CONTROL_MODE_SINGLE_COMMAND:
                return await self.async_step_single_command()
            return await self.async_step_two_commands()
        return self.async_show_form(step_id="user", data_schema=CONTROL_MODE_SCHEMA)

    async def async_step_two_commands(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self._async_finish(CONTROL_MODE_TWO_COMMANDS, user_input)
        return self.async_show_form(step_id="two_commands", data_schema=TWO_COMMANDS_SCHEMA)

    async def async_step_single_command(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self._async_finish(CONTROL_MODE_SINGLE_COMMAND, user_input)
        return self.async_show_form(step_id="single_command", data_schema=SINGLE_COMMAND_SCHEMA)

    def _async_finish(self, control_mode: str, user_input: dict[str, Any]) -> ConfigFlowResult:
        user_input[CONF_CONTROL_MODE] = control_mode
        user_input[CONF_SUBSCRIPTION_KVA] = int(user_input[CONF_SUBSCRIPTION_KVA])
        return self.async_create_entry(title="Glorp's Battery Optimization", data=user_input)
