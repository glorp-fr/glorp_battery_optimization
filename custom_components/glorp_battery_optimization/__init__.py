"""Glorp's Battery Optimization integration.

Deliberately keeps this module import-safe without Home Assistant installed
(only `.const` is imported at module load time) so the pure decision logic
can be unit tested without a full HA environment. `homeassistant` and
`.controller` are only imported inside the functions that need them, once
Home Assistant is actually running this code.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .const import DOMAIN, PLATFORMS

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


async def async_setup_entry(hass: "HomeAssistant", entry: "ConfigEntry") -> bool:
    """Set up Glorp's Battery Optimization from a config entry."""
    from .controller import ZendureOptimizationController

    hass.data.setdefault(DOMAIN, {})
    controller = ZendureOptimizationController(hass, entry)
    hass.data[DOMAIN][entry.entry_id] = controller
    await controller.async_start()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: "HomeAssistant", entry: "ConfigEntry") -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        controller = hass.data[DOMAIN].pop(entry.entry_id)
        controller.async_stop()
    return unload_ok


async def _async_update_listener(hass: "HomeAssistant", entry: "ConfigEntry") -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)
