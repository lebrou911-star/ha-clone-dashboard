"""Config flow for Dashboard Copy.

A minimal single-instance setup. Adding the integration registers the
``dashboard_copy.copy`` service; the actual duplication is done by calling that
service from Developer Tools -> Actions (or an automation), not from this flow.
"""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN


class DashboardCopyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the (one-time) setup of Dashboard Copy."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create the single config entry that enables the copy service."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            return self.async_create_entry(title="Dashboard Copy", data={})

        return self.async_show_form(step_id="user")
