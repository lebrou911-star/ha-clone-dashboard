# Dashboard Copy

A small Home Assistant custom integration that **duplicates a Lovelace dashboard
into a new one** — via a service you call from the UI, no YAML editing.

## What it does

Adds a service **`dashboard_copy.copy`** (Developer Tools → Actions). Fields:

- **Source dashboard** (`source`) — URL path of the dashboard to copy (the part
  after `/lovelace/`). Use `lovelace` for the default Overview.
- **New title** (`new_title`).
- **New URL path** (`new_url_path`) — optional; auto-derived from the title if
  left blank (a `-` is added if needed, since HA requires it).
- **Rewrite navigation links** (`update_links`, default on) — any
  `navigation_path` in the copied config that points at the *source* dashboard
  (e.g. `/source-dash/view`) is rewritten to the *new* dashboard
  (`/new-dash/view`), so the copy is self-contained. Relative anchors
  (Bubble Card `#pop-up`, intra-view `#view`) and external URLs are left alone.

The service returns the new dashboard's `url_path` as a response.

## Install (HACS)

1. HACS → ⋮ → *Custom repositories* → add
   `https://github.com/lebrou911-star/ha-clone-dashboard`, category **Integration**.
2. Install **Dashboard Copy**.
3. Restart Home Assistant.
4. **Settings → Devices & services → Add integration → Dashboard Copy** (one-time;
   this registers the service).

## Usage

**Developer Tools → Actions → `Dashboard Copy: Copy dashboard`**, fill the fields,
and run. Or in YAML / an automation:

```yaml
action: dashboard_copy.copy
data:
  source: lovelace
  new_title: My copy
  new_url_path: my-copy   # optional
  update_links: true
```

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
