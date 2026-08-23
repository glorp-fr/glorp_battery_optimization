"""Live-adjustable numeric thresholds, persisted across restarts."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import NumberEntityDescription, NumberMode, RestoreNumber
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DEFAULT_DEADBAND_W,
    DEFAULT_MODE_SWITCH_HYSTERESIS_W,
    DEFAULT_NIGHT_CHARGE_POWER,
    DEFAULT_NIGHT_CHARGE_SOC_THRESHOLD,
    DEFAULT_SOC_MAX,
    DEFAULT_SOC_MIN,
    DEFAULT_SUBSCRIPTION_MARGIN_W,
    DOMAIN,
    SETTING_DEADBAND_W,
    SETTING_MODE_SWITCH_HYSTERESIS_W,
    SETTING_NIGHT_CHARGE_POWER,
    SETTING_NIGHT_CHARGE_SOC_THRESHOLD,
    SETTING_SOC_MAX,
    SETTING_SOC_MIN,
    SETTING_SUBSCRIPTION_MARGIN_W,
)


@dataclass(frozen=True)
class SettingNumberDescription:
    key: str
    translation_key: str
    default: float
    min_value: float
    max_value: float
    step: float
    unit: str | None


NUMBERS = [
    SettingNumberDescription(SETTING_SOC_MIN, "soc_min", DEFAULT_SOC_MIN, 0, 50, 1, "%"),
    SettingNumberDescription(SETTING_SOC_MAX, "soc_max", DEFAULT_SOC_MAX, 50, 100, 1, "%"),
    SettingNumberDescription(
        SETTING_NIGHT_CHARGE_SOC_THRESHOLD, "night_charge_soc_threshold", DEFAULT_NIGHT_CHARGE_SOC_THRESHOLD, 0, 100, 1, "%"
    ),
    SettingNumberDescription(SETTING_NIGHT_CHARGE_POWER, "night_charge_power", DEFAULT_NIGHT_CHARGE_POWER, 0, 12000, 50, "W"),
    SettingNumberDescription(SETTING_DEADBAND_W, "deadband_w", DEFAULT_DEADBAND_W, 0, 500, 5, "W"),
    SettingNumberDescription(
        SETTING_SUBSCRIPTION_MARGIN_W, "subscription_margin_w", DEFAULT_SUBSCRIPTION_MARGIN_W, 0, 5000, 50, "W"
    ),
    SettingNumberDescription(
        SETTING_MODE_SWITCH_HYSTERESIS_W, "mode_switch_hysteresis_w", DEFAULT_MODE_SWITCH_HYSTERESIS_W, 0, 1000, 10, "W"
    ),
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    controller = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(SettingNumber(entry, controller, desc) for desc in NUMBERS)


class SettingNumber(RestoreNumber):
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_mode = NumberMode.BOX

    def __init__(self, entry: ConfigEntry, controller, desc: SettingNumberDescription) -> None:
        self._controller = controller
        self._desc = desc
        self._attr_unique_id = f"{entry.entry_id}_{desc.key}"
        self._attr_translation_key = desc.translation_key
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)}, name=entry.title)
        self.entity_description = NumberEntityDescription(
            key=desc.key,
            native_min_value=desc.min_value,
            native_max_value=desc.max_value,
            native_step=desc.step,
            native_unit_of_measurement=desc.unit,
        )
        self._attr_native_value = desc.default
        controller.settings[desc.key] = desc.default

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_data = await self.async_get_last_number_data()
        if last_data is not None and last_data.native_value is not None:
            self._attr_native_value = last_data.native_value
            self._controller.settings[self._desc.key] = last_data.native_value

    async def async_set_native_value(self, value: float) -> None:
        self._attr_native_value = value
        self._controller.settings[self._desc.key] = value
        self.async_write_ha_state()
        await self._controller.async_run_cycle()
