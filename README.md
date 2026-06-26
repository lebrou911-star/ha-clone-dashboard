# Dashboard Copy

A small Home Assistant custom integration that **duplicates a Lovelace dashboard
into a new one** — entirely from the UI, no YAML.

## What it does

Adds an "action-style" config flow. You pick:

- **Dashboard to copy** — a live dropdown of every existing dashboard (including
  the default Overview).
- **New dashboard title**.
- **URL path** — optional; auto-derived from the title if left blank (a `-` is
  added if needed, since HA requires it).
- **Rewrite navigation links** — when enabled, any `navigation_path` in the
  copied config that points at the *source* dashboard (e.g.
  `/source-dash/view`) is rewritten to the *new* dashboard
  (`/new-dash/view`), so the copy is self-contained. Relative anchors
  (Bubble Card `#pop-up`, intra-view `#view`) and external URLs are left alone.

The flow performs the copy and then closes — it does **not** create a config
entry, so nothing lingers. Run it again any time from
**Settings → Devices & services → Add integration → Dashboard Copy**.

## Install (HACS)

1. HACS → ⋮ → *Custom repositories* → add
   `https://github.com/lebrou911-star/ha-clone-dashboard`, category **Integration**.
2. Install **Dashboard Copy**.
3. Restart Home Assistant.
4. **Settings → Devices & services → Add integration → Dashboard Copy**.

After a copy, hard-refresh the browser (Ctrl+Shift+R) to see the new dashboard
in the sidebar.

## Notes

- Only the dashboard **content** is copied. Theme keys (`theme:` at view/card
  level), `card_mod`, and custom cards are preserved as-is by a deep copy.
- The source can be a storage **or** YAML-mode dashboard; the new dashboard is
  always created in storage mode.
- `show_in_sidebar` is on and `require_admin` off by default for the new
  dashboard; adjust afterwards in the dashboard settings if needed.

## License

MIT
