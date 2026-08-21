"""Per-strategy enable switches, persisted across restarts."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    DOMAIN,
    SETTING_ENABLE_NIGHT_CHARGE,
    SETTING_ENABLE_SOLAR_CHARGE,
    SETTING_ENABLE_ZERO_EXPORT,
    SETTING_MASTER_ENABLE,
)


@dataclass(frozen=True)
class SettingSwitchDescription:
    key: str
    translation_key: str


SWITCHES = [
    SettingSwitchDescription(SETTING_MASTER_ENABLE, "master_enable"),
    SettingSwitchDescription(SETTING_ENABLE_NIGHT_CHARGE, "enable_night_charge"),
    SettingSwitchDescription(SETTING_ENABLE_SOLAR_CHARGE, "enable_solar_charge"),
    SettingSwitchDescription(SETTING_ENABLE_ZERO_EXPORT, "enable_zero_export"),
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    controller = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(SettingSwitch(entry, controller, desc) for desc in SWITCHES)


class SettingSwitch(SwitchEntity, RestoreEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, controller, desc: SettingSwitchDescription) -> None:
        self._controller = controller
        self._desc = desc
        self._attr_unique_id = f"{entry.entry_id}_{desc.key}"
        self._attr_translation_key = desc.translation_key
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)}, name=entry.title)
        self._attr_is_on = True
        controller.settings[desc.key] = True

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state in ("on", "off"):
            is_on = last_state.state == "on"
            self._attr_is_on = is_on
            self._controller.settings[self._desc.key] = is_on

    async def async_turn_on(self, **kwargs) -> None:
        self._attr_is_on = True
        self._controller.settings[self._desc.key] = True
        self.async_write_ha_state()
        await self._controller.async_run_cycle()

    async def async_turn_off(self, **kwargs) -> None:
        self._attr_is_on = False
        self._controller.settings[self._desc.key] = False
        self.async_write_ha_state()
        await self._controller.async_run_cycle()
