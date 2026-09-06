# Local Contributions

GitHub-style contribution heatmap of **git commits on this machine** — Hermes desktop plugin + Python scanner.

Not GitHub.com. Not the Omarchy agents token panel. Squares are days you actually committed locally.

## Layout

```
plugin.yaml                 Hermes agent plugin manifest
__init__.py                 no tools — backend is dashboard API only
dashboard/plugin_api.py     scans git, serves /api/plugins/local-contrib
desktop/plugin.js           Garden page, sidebar, status chip
```

Hermes loads from:

| Live path | Points at |
|---|---|
| `~/.hermes/plugins/local-contrib` | this repo (Python) |
| `~/.hermes/desktop-plugins/local-contrib` | `desktop/` (UI) |

Those are symlinks. Edit here; Hermes picks it up.

## Reload / see it

**Desktop UI** (heatmap, sidebar **Garden**, status chip)

1. Command palette (`Ctrl+K` / `⌘K`) → **Reload desktop plugins**
2. Saving `desktop/plugin.js` also hot-reloads within a few seconds
3. Sidebar **Garden**, or palette **Open local contributions**

If Garden is missing: Settings → Plugins → enable **Local Contributions**.

**Git scanner** (the numbers behind the squares)

Python routes mount when the gateway starts. After the first install, or after changing `dashboard/plugin_api.py`:

- Quit and reopen Hermes, **or**
- Start a new Hermes session so `serve` comes back up

`hermes plugins enable local-contrib` is already done on this machine.

## What it counts

- Repos under `~/projects` and `~/Documents` (override in `~/.hermes/state/local-contrib.json`)
- Commits matching your git `user.name` / `user.email` (so personal + work mail both count if the name matches)
- No merges, last ~4 years scanned, rolling last-year grid by default

## Develop

```bash
# UI: edit, save, palette → Reload desktop plugins
$EDITOR desktop/plugin.js

# Scanner: edit, then restart Hermes
$EDITOR dashboard/plugin_api.py

# Smoke the scanner without the app
python3 -c 'import sys; sys.path.insert(0,"dashboard"); import plugin_api as p; s=p.build_snapshot(force=True); print(s["total"], s["today"])'
```
