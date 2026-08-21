"""Live-adjustable off-peak window boundaries, persisted across restarts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time as dt_time

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from .const import DEFAULT_OFF_PEAK_END, DEFAULT_OFF_PEAK_START, DOMAIN, SETTING_OFF_PEAK_END, SETTING_OFF_PEAK_START


@dataclass(frozen=True)
class SettingTimeDescription:
    key: str
    translation_key: str
    default: str


TIMES = [
    SettingTimeDescription(SETTING_OFF_PEAK_START, "off_peak_start", DEFAULT_OFF_PEAK_START),
    SettingTimeDescription(SETTING_OFF_PEAK_END, "off_peak_end", DEFAULT_OFF_PEAK_END),
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    controller = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(SettingTime(entry, controller, desc) for desc in TIMES)


class SettingTime(TimeEntity, RestoreEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, controller, desc: SettingTimeDescription) -> None:
        self._controller = controller
        self._desc = desc
        self._attr_unique_id = f"{entry.entry_id}_{desc.key}"
        self._attr_translation_key = desc.translation_key
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)}, name=entry.title)
        default_time = dt_util.parse_time(desc.default)
        self._attr_native_value = default_time
        controller.settings[desc.key] = default_time

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state not in ("unknown", "unavailable"):
            parsed = dt_util.parse_time(last_state.state)
            if parsed is not None:
                self._attr_native_value = parsed
                self._controller.settings[self._desc.key] = parsed

    async def async_set_value(self, value: dt_time) -> None:
        self._attr_native_value = value
        self._controller.settings[self._desc.key] = value
        self.async_write_ha_state()
        await self._controller.async_run_cycle()
