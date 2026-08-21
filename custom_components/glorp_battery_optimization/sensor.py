"""Read-only sensors reflecting the controller's last decision."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, REASON_IDLE


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    controller = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ActiveModeSensor(entry, controller), DecisionReasonSensor(entry, controller)])


class _ControllerSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, controller) -> None:
        self._entry = entry
        self._controller = controller
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)}, name=entry.title)

    async def async_added_to_hass(self) -> None:
        self._controller.register_sensor_callback(self.async_write_ha_state)


class ActiveModeSensor(_ControllerSensor):
    _attr_translation_key = "active_mode"

    def __init__(self, entry: ConfigEntry, controller) -> None:
        super().__init__(entry, controller)
        self._attr_unique_id = f"{entry.entry_id}_active_mode"

    @property
    def native_value(self) -> str:
        decision = self._controller.last_decision
        if decision is None or not decision["active"] or decision["mode"] is None:
            return "idle"
        return "charging" if decision["mode"] == "input" else "discharging"


class DecisionReasonSensor(_ControllerSensor):
    _attr_translation_key = "decision_reason"

    def __init__(self, entry: ConfigEntry, controller) -> None:
        super().__init__(entry, controller)
        self._attr_unique_id = f"{entry.entry_id}_decision_reason"

    @property
    def native_value(self) -> str:
        decision = self._controller.last_decision
        if decision is None:
            return REASON_IDLE
        return decision["reason"]
