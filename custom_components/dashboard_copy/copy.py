"""Core dashboard-duplication logic, shared by the service handler."""

from __future__ import annotations

import copy
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import slugify

from .const import DEFAULT_SENTINEL

_LOGGER = logging.getLogger(__name__)

# Home Assistant's lovelace domain and storage panel mode.
_LOVELACE_DOMAIN = "lovelace"
_MODE_STORAGE = "storage"
_DEFAULT_ICON = "mdi:view-dashboard"
_WS_CREATE_COMMAND = "lovelace/dashboards/create"

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


def _find_live_dashboards_collection(hass: HomeAssistant):
    """Return the running DashboardsCollection, or None if unreachable.

    Recent HA versions no longer expose the collection on LovelaceData, so we
    recover it from the registered ``lovelace/dashboards/create`` websocket
    command, whose handler is bound to the StorageCollectionWebsocket that holds
    the live collection. Using the live instance means HA's own listener wires
    the new dashboard into the sidebar and the dashboards registry for us.
    """
    # Some versions may still keep it directly in hass.data.
    for value in hass.data.values():
        if type(value).__name__ == "DashboardsCollection":
            return value

    for value in hass.data.values():
        if not isinstance(value, dict) or _WS_CREATE_COMMAND not in value:
            continue
        entry = value[_WS_CREATE_COMMAND]
        handler = entry[0] if isinstance(entry, (tuple, list)) else entry
        ws_obj = getattr(handler, "__self__", None)
        coll = getattr(ws_obj, "storage_collection", None)
        if coll is not None and type(coll).__name__ == "DashboardsCollection":
            return coll
    return None


async def _create_storage_dashboard(
    hass: HomeAssistant, lovelace: Any, item_data: dict[str, Any]
) -> None:
    """Create a storage dashboard and wire it into the running instance.

    Leaves ``lovelace.dashboards[url_path]`` populated so the caller can save
    the copied config into it.
    """
    url_path = item_data["url_path"]

    live = _find_live_dashboards_collection(hass)
    if live is not None:
        # The collection's change listener inserts the LovelaceStorage into
        # lovelace.dashboards and registers the sidebar panel.
        await live.async_create_item(item_data)
        return

    # Fallback: drive a fresh collection (persists to the same store) and wire
    # the dashboard + panel ourselves, mirroring HA's internal listener.
    from homeassistant.components import frontend
    from homeassistant.components.lovelace.dashboard import (
        DashboardsCollection,
        LovelaceStorage,
    )

    collection = DashboardsCollection(hass)
    await collection.async_load()
    item = await collection.async_create_item(item_data)

    lovelace.dashboards[url_path] = LovelaceStorage(hass, item)
    try:
        frontend.async_register_built_in_panel(
            hass,
            _LOVELACE_DOMAIN,
            frontend_url_path=url_path,
            require_admin=item.get("require_admin", False),
            sidebar_title=item.get("title"),
            sidebar_icon=item.get("icon", _DEFAULT_ICON),
            show_in_sidebar=item.get("show_in_sidebar", True),
            config={"mode": _MODE_STORAGE},
            update=False,
        )
    except ValueError:
        _LOGGER.warning("Could not register sidebar panel for %s", url_path)


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

    try:
        await _create_storage_dashboard(
            hass,
            lovelace,
            {
                "url_path": new_url,
                "title": new_title or new_url,
                "icon": "mdi:content-copy",
                "show_in_sidebar": True,
                "require_admin": False,
            },
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
