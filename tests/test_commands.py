"""Unit tests for build_commands(). No Home Assistant needed."""

from custom_components.glorp_battery_optimization.const import (
    AC_MODE_INPUT,
    AC_MODE_OUTPUT,
    CONTROL_MODE_SINGLE_COMMAND,
    CONTROL_MODE_TWO_COMMANDS,
    POWER_SIGN_POSITIVE_CHARGE,
    POWER_SIGN_POSITIVE_DISCHARGE,
)
from custom_components.glorp_battery_optimization.commands import build_commands

TWO_COMMANDS_ENTRY_DATA = {
    "ac_mode_entity": "select.battery_ac_mode",
    "input_limit_entity": "number.battery_input_limit",
    "output_limit_entity": "number.battery_output_limit",
}

SINGLE_COMMAND_ENTRY_DATA = {
    "power_entity": "number.battery_power",
    "power_sign": POWER_SIGN_POSITIVE_DISCHARGE,
}


def _decision(mode, power_w):
    return {"active": True, "mode": mode, "power_w": power_w, "reason": "test"}


def test_two_commands_charge():
    commands = build_commands(CONTROL_MODE_TWO_COMMANDS, _decision(AC_MODE_INPUT, 400), TWO_COMMANDS_ENTRY_DATA)
    assert commands == [
        ("select", "select_option", {"entity_id": "select.battery_ac_mode", "option": "input"}),
        ("number", "set_value", {"entity_id": "number.battery_output_limit", "value": 0}),
        ("number", "set_value", {"entity_id": "number.battery_input_limit", "value": 400}),
    ]


def test_two_commands_discharge():
    commands = build_commands(CONTROL_MODE_TWO_COMMANDS, _decision(AC_MODE_OUTPUT, 700), TWO_COMMANDS_ENTRY_DATA)
    assert commands == [
        ("select", "select_option", {"entity_id": "select.battery_ac_mode", "option": "output"}),
        ("number", "set_value", {"entity_id": "number.battery_input_limit", "value": 0}),
        ("number", "set_value", {"entity_id": "number.battery_output_limit", "value": 700}),
    ]


def test_two_commands_stop():
    commands = build_commands(CONTROL_MODE_TWO_COMMANDS, _decision(None, 0), TWO_COMMANDS_ENTRY_DATA)
    assert commands == [
        ("number", "set_value", {"entity_id": "number.battery_input_limit", "value": 0}),
        ("number", "set_value", {"entity_id": "number.battery_output_limit", "value": 0}),
    ]


def test_single_command_charge_positive_discharge_convention():
    # power_sign=positive_discharge means charging must be written negative.
    commands = build_commands(CONTROL_MODE_SINGLE_COMMAND, _decision(AC_MODE_INPUT, 400), SINGLE_COMMAND_ENTRY_DATA)
    assert commands == [("number", "set_value", {"entity_id": "number.battery_power", "value": -400})]


def test_single_command_discharge_positive_discharge_convention():
    commands = build_commands(CONTROL_MODE_SINGLE_COMMAND, _decision(AC_MODE_OUTPUT, 700), SINGLE_COMMAND_ENTRY_DATA)
    assert commands == [("number", "set_value", {"entity_id": "number.battery_power", "value": 700})]


def test_single_command_charge_positive_charge_convention():
    entry_data = {**SINGLE_COMMAND_ENTRY_DATA, "power_sign": POWER_SIGN_POSITIVE_CHARGE}
    commands = build_commands(CONTROL_MODE_SINGLE_COMMAND, _decision(AC_MODE_INPUT, 400), entry_data)
    assert commands == [("number", "set_value", {"entity_id": "number.battery_power", "value": 400})]


def test_single_command_discharge_positive_charge_convention():
    entry_data = {**SINGLE_COMMAND_ENTRY_DATA, "power_sign": POWER_SIGN_POSITIVE_CHARGE}
    commands = build_commands(CONTROL_MODE_SINGLE_COMMAND, _decision(AC_MODE_OUTPUT, 700), entry_data)
    assert commands == [("number", "set_value", {"entity_id": "number.battery_power", "value": -700})]


def test_single_command_stop():
    commands = build_commands(CONTROL_MODE_SINGLE_COMMAND, _decision(None, 0), SINGLE_COMMAND_ENTRY_DATA)
    assert commands == [("number", "set_value", {"entity_id": "number.battery_power", "value": 0})]
