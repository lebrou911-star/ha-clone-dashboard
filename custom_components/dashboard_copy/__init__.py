"""Dashboard Copy — duplicate a Lovelace dashboard into a new one.

This is a flow-only integration: the config flow performs the copy action and
then aborts, so no config entry is ever created. The stubs below exist only so
Home Assistant treats the integration normally should an entry ever appear.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """No-op: this integration does not create persistent entries."""
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """No-op unload."""
    return True
