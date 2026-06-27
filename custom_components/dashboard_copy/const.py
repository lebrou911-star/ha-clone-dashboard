"""Constants for the Dashboard Copy integration."""

DOMAIN = "dashboard_copy"

# Service exposed by the integration (Developer Tools -> Actions).
SERVICE_COPY = "copy"

# Service field names.
CONF_SOURCE = "source"
CONF_NEW_TITLE = "new_title"
CONF_NEW_URL_PATH = "new_url_path"
CONF_UPDATE_LINKS = "update_links"

# Sentinel value used for the default "Overview" dashboard, whose internal key
# in the lovelace data is None and whose URL path is "lovelace".
DEFAULT_SENTINEL = "lovelace"
