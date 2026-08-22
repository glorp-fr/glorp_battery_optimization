"""Translate a Decision into the service calls that apply it to the device.

Deliberately framework-free, like `decision.py`: given a control mode, a
Decision, and the config entry's data, it returns the list of Home Assistant
service calls to make. It never calls a service itself, so it's testable with
plain pytest.
"""

from __future__ import annotations

from typing import Any

from .const import (
    AC_MODE_INPUT,
    CONF_AC_MODE_ENTITY,
    CONF_INPUT_LIMIT_ENTITY,
    CONF_OUTPUT_LIMIT_ENTITY,
    CONF_POWER_ENTITY,
    CONF_POWER_SIGN,
    CONTROL_MODE_SINGLE_COMMAND,
    POWER_SIGN_POSITIVE_CHARGE,
    POWER_SIGN_POSITIVE_DISCHARGE,
)
from .decision import Decision

# (domain, service, service_data) — as passed to hass.services.async_call().
Command = tuple[str, str, dict[str, Any]]


def build_commands(control_mode: str, result: Decision, entry_data: dict[str, Any]) -> list[Command]:
    """Return the service calls needed to apply `result` under `control_mode`."""
    if control_mode == CONTROL_MODE_SINGLE_COMMAND:
        return _build_single_command(result, entry_data)
    return _build_two_commands(result, entry_data)


def _build_two_commands(result: Decision, entry_data: dict[str, Any]) -> list[Command]:
    ac_mode_entity = entry_data[CONF_AC_MODE_ENTITY]
    input_limit_entity = entry_data[CONF_INPUT_LIMIT_ENTITY]
    output_limit_entity = entry_data[CONF_OUTPUT_LIMIT_ENTITY]

    if result["mode"] == AC_MODE_INPUT:
        return [
            ("select", "select_option", {"entity_id": ac_mode_entity, "option": AC_MODE_INPUT}),
            ("number", "set_value", {"entity_id": output_limit_entity, "value": 0}),
            ("number", "set_value", {"entity_id": input_limit_entity, "value": result["power_w"]}),
        ]
    if result["mode"] is not None:  # output / discharge
        return [
            ("select", "select_option", {"entity_id": ac_mode_entity, "option": result["mode"]}),
            ("number", "set_value", {"entity_id": input_limit_entity, "value": 0}),
            ("number", "set_value", {"entity_id": output_limit_entity, "value": result["power_w"]}),
        ]
    # stop
    return [
        ("number", "set_value", {"entity_id": input_limit_entity, "value": 0}),
        ("number", "set_value", {"entity_id": output_limit_entity, "value": 0}),
    ]


def _build_single_command(result: Decision, entry_data: dict[str, Any]) -> list[Command]:
    power_entity = entry_data[CONF_POWER_ENTITY]
    sign = entry_data[CONF_POWER_SIGN]

    signed_power_w = 0
    if result["mode"] == AC_MODE_INPUT:
        signed_power_w = result["power_w"] if sign == POWER_SIGN_POSITIVE_CHARGE else -result["power_w"]
    elif result["mode"] is not None:  # output / discharge
        signed_power_w = result["power_w"] if sign == POWER_SIGN_POSITIVE_DISCHARGE else -result["power_w"]

    return [("number", "set_value", {"entity_id": power_entity, "value": signed_power_w})]
