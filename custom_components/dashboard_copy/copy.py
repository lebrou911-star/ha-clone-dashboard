"""Core dashboard-duplication logic, shared by the service handler."""

from __future__ import annotations

import copy
import dataclasses
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import slugify

from .const import DEFAULT_SENTINEL

_LOGGER = logging.getLogger(__name__)

# Human-readable messages keyed by CopyError.code.
ERROR_MESSAGES: dict[str, str] = {
    "source_not_found": "Source dashboard not found.",
    "url_taken": "A dashboard with that URL path already exists.",
    "load_failed": "Could not load the source dashboard.",
    "create_failed": "Could not create the new dashboard.",
    "save_failed": "Could not save the new dashboard configuration.",
}


class CopyError(Exception):
    """Raised when a copy step fails; ``code`` maps to ERROR_MESSAGES."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code

    @property
    def message(self) -> str:
        return ERROR_MESSAGES.get(self.code, "Unknown error while copying dashboard.")


def _get_lovelace(hass: HomeAssistant):
    """Return the LovelaceData object across HA versions."""
    try:
        from homeassistant.components.lovelace.const import LOVELACE_DATA

        return hass.data[LOVELACE_DATA]
    except (ImportError, KeyError):
        return hass.data["lovelace"]


def _get_dashboards_collection(lovelace: Any):
    """Locate the storage DashboardsCollection regardless of HA version.

    The attribute holding it on LovelaceData has been renamed across versions
    (``dashboards_collection`` / ``dashboard_collection`` / dict key), so fall
    back to identifying it by its class instead of a fixed name.
    """
    for attr in ("dashboards_collection", "dashboard_collection"):
        coll = getattr(lovelace, attr, None)
        if coll is not None:
            return coll

    if isinstance(lovelace, dict):
        candidates: list[Any] = list(lovelace.values())
    elif dataclasses.is_dataclass(lovelace):
        candidates = [getattr(lovelace, f.name, None) for f in dataclasses.fields(lovelace)]
    else:
        candidates = list(getattr(lovelace, "__dict__", {}).values())

    for value in candidates:
        if type(value).__name__ == "DashboardsCollection":
            return value
    return None


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


async def async_perform_copy(
    hass: HomeAssistant,
    *,
    source: str,
    new_title: str,
    new_url_path: str | None = None,
    update_links: bool = True,
) -> str:
    """Duplicate a dashboard. Returns the new url_path or raises CopyError."""
    lovelace = _get_lovelace(hass)

    source_key = None if source == DEFAULT_SENTINEL else source
    if source_key not in lovelace.dashboards:
        raise CopyError("source_not_found")
    source_dash = lovelace.dashboards[source_key]

    new_title = (new_title or "").strip()
    raw_url = (new_url_path or "").strip()
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

    if update_links:
        source_url = source_key if source_key is not None else DEFAULT_SENTINEL
        _rewrite_navigation(new_config, source_url, new_url)

    collection = _get_dashboards_collection(lovelace)
    if collection is None:
        _LOGGER.error("Could not locate the lovelace DashboardsCollection")
        raise CopyError("create_failed")

    try:
        await collection.async_create_item(
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

    _LOGGER.info("Copied dashboard '%s' -> '%s'", source, new_url)
    return new_url
