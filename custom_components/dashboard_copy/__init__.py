"""Dashboard Copy — duplicate a Lovelace dashboard into a new one.

Setting up the integration (a single, UI-added instance) registers the
``dashboard_copy.copy`` service, which performs the duplication. Call it from
Developer Tools -> Actions or from any automation/script.
"""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import ServiceValidationError
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_NEW_TITLE,
    CONF_NEW_URL_PATH,
    CONF_SOURCE,
    CONF_UPDATE_LINKS,
    DOMAIN,
    SERVICE_COPY,
)
from .copy import CopyError, async_perform_copy

_LOGGER = logging.getLogger(__name__)

SERVICE_COPY_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SOURCE): cv.string,
        vol.Required(CONF_NEW_TITLE): cv.string,
        vol.Optional(CONF_NEW_URL_PATH): cv.string,
        vol.Optional(CONF_UPDATE_LINKS, default=True): cv.boolean,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Register the dashboard_copy.copy service."""

    async def handle_copy(call: ServiceCall) -> ServiceResponse:
        try:
            new_url = await async_perform_copy(
                hass,
                source=call.data[CONF_SOURCE],
                new_title=call.data[CONF_NEW_TITLE],
                new_url_path=call.data.get(CONF_NEW_URL_PATH),
                update_links=call.data.get(CONF_UPDATE_LINKS, True),
            )
        except CopyError as err:
            raise ServiceValidationError(err.message) from err
        return {"url_path": new_url}

    if not hass.services.has_service(DOMAIN, SERVICE_COPY):
        hass.services.async_register(
            DOMAIN,
            SERVICE_COPY,
            handle_copy,
            schema=SERVICE_COPY_SCHEMA,
            supports_response=SupportsResponse.OPTIONAL,
        )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Remove the service when the integration is removed."""
    hass.services.async_remove(DOMAIN, SERVICE_COPY)
    return True
