"""Config flow for Dashboard Copy.

Action-style flow: shows a form (live dropdown of existing dashboards, new
title, optional URL path, and an "update links" toggle), performs the copy,
then aborts. No config entry is created.
"""

from __future__ import annotations

import copy
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import selector
from homeassistant.util import slugify

from .const import DEFAULT_SENTINEL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class CopyError(Exception):
    """Raised when a copy step fails; ``code`` maps to a strings.json error key."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _get_lovelace(hass):
    """Return the LovelaceData object across HA versions."""
    try:
        from homeassistant.components.lovelace.const import LOVELACE_DATA

        return hass.data[LOVELACE_DATA]
    except (ImportError, KeyError):
        return hass.data["lovelace"]


def _dashboard_choices(hass) -> list[selector.SelectOptionDict]:
    """Build the dropdown of copyable dashboards (live)."""
    lovelace = _get_lovelace(hass)

    titles: dict[str, str] = {}
    try:
        for item in lovelace.dashboards_collection.async_items():
            titles[item["url_path"]] = item.get("title", item["url_path"])
    except Exception:  # noqa: BLE001 - defensive: never block the form
        _LOGGER.debug("Could not read dashboard titles", exc_info=True)

    choices: list[selector.SelectOptionDict] = []
    for url_path in lovelace.dashboards:
        if url_path is None:
            choices.append(
                selector.SelectOptionDict(
                    value=DEFAULT_SENTINEL, label="Overview (lovelace)"
                )
            )
        else:
            label = titles.get(url_path, url_path)
            choices.append(
                selector.SelectOptionDict(
                    value=url_path, label=f"{label} ({url_path})"
                )
            )
    choices.sort(key=lambda c: c["label"].lower())
    return choices


def _normalize_url_path(value: str) -> str:
    """Turn a title or raw input into a valid storage dashboard url_path.

    HA requires the url_path to be a lowercase slug containing at least one '-'.
    """
    slug = slugify(value).replace("_", "-")
    if not slug:
        slug = "copie"
    if "-" not in slug:
        slug = f"{slug}-dashboard"
    return slug


def _rewrite_navigation(obj: Any, source_url: str, new_url: str) -> None:
    """Recursively rewrite navigation_path values pointing at the source dashboard.

    Only absolute paths starting with '/<source_url>' are rewritten to
    '/<new_url>'. Relative anchors (e.g. Bubble Card '#pop-up') and external
    URLs are left untouched.
    """
    old_prefix = f"/{source_url}"
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == "navigation_path" and isinstance(value, str):
                if value == old_prefix or value.startswith(old_prefix + "/"):
                    obj[key] = f"/{new_url}" + value[len(old_prefix):]
            else:
                _rewrite_navigation(value, source_url, new_url)
    elif isinstance(obj, list):
        for item in obj:
            _rewrite_navigation(item, source_url, new_url)


class DashboardCopyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the copy flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the copy form and run the copy on submit."""
        errors: dict[str, str] = {}
        choices = _dashboard_choices(self.hass)

        if not choices:
            return self.async_abort(reason="no_dashboards")

        if user_input is not None:
            try:
                new_url = await self._do_copy(user_input)
            except CopyError as err:
                errors["base"] = err.code
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error while copying dashboard")
                errors["base"] = "unknown"
            else:
                return self.async_abort(
                    reason="copy_successful",
                    description_placeholders={"url": new_url},
                )

        schema = vol.Schema(
            {
                vol.Required("source"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=choices,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required("new_title"): selector.TextSelector(),
                vol.Optional("new_url_path"): selector.TextSelector(),
                vol.Required("update_links", default=True): selector.BooleanSelector(),
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )

    async def _do_copy(self, user_input: dict[str, Any]) -> str:
        """Perform the actual dashboard duplication. Returns the new url_path."""
        hass = self.hass
        lovelace = _get_lovelace(hass)

        source_value = user_input["source"]
        source_key = None if source_value == DEFAULT_SENTINEL else source_value

        if source_key not in lovelace.dashboards:
            raise CopyError("source_not_found")
        source_dash = lovelace.dashboards[source_key]

        new_title = (user_input.get("new_title") or "").strip()
        raw_url = (user_input.get("new_url_path") or "").strip()
        new_url = _normalize_url_path(raw_url or new_title)

        existing = {k for k in lovelace.dashboards if k is not None}
        existing.add(DEFAULT_SENTINEL)
        if new_url in existing:
            raise CopyError("url_taken")

        try:
            config = await source_dash.async_load(False)
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Could not load source dashboard %s: %s", source_key, err)
            raise CopyError("load_failed") from err

        if not config:
            raise CopyError("load_failed")

        new_config = copy.deepcopy(config)
        if new_title:
            new_config["title"] = new_title

        if user_input.get("update_links", True):
            source_url = source_key if source_key is not None else DEFAULT_SENTINEL
            _rewrite_navigation(new_config, source_url, new_url)

        try:
            await lovelace.dashboards_collection.async_create_item(
                {
                    "url_path": new_url,
                    "title": new_title or new_url,
                    "icon": "mdi:content-copy",
                    "show_in_sidebar": True,
                    "require_admin": False,
                }
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Could not create dashboard %s: %s", new_url, err)
            raise CopyError("create_failed") from err

        new_dash = lovelace.dashboards.get(new_url)
        if new_dash is None:
            raise CopyError("create_failed")

        try:
            await new_dash.async_save(new_config)
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Could not save config to %s: %s", new_url, err)
            raise CopyError("save_failed") from err

        _LOGGER.info("Copied dashboard '%s' -> '%s'", source_value, new_url)
        return new_url
