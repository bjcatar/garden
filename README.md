# Garden

Omarchy bar widget: GitHub-style contribution heatmap of **git commits on this machine**.

Not the Agents token panel. Not github.com. Squares are days you actually committed locally.

## Install (this machine)

The widget lives in the repo and is copied into Omarchy’s plugin dir:

```bash
rsync -a --delete --exclude .git --exclude hermes \
  ~/Projects/personal/local-contrib/ ~/.config/omarchy/plugins/bjcatar.garden/
omarchy plugin validate ~/.config/omarchy/plugins/bjcatar.garden
omarchy plugin enable bjcatar.garden --section right
omarchy-shell shell rescanPlugins
```

Bar pill: last 7 days as tiny squares. Left-click opens the year grid. Middle-click refreshes. `r` in the panel rescans.

## Reload after editing

Omarchy is not Hermes. Super+K is the Omarchy launcher; Ctrl+K is Hermes.

- Saving a file under `~/.config/omarchy/plugins/bjcatar.garden/` reloads the widget
- If it doesn’t: `omarchy-shell shell rescanPlugins`
- Still stuck: `omarchy restart shell`

Edit the **repo**, then rsync (or edit the copy under `~/.config/omarchy/plugins/` directly).

## What it counts

`bin/garden-scan` walks `~/Projects` and `~/Documents`, keeps commits matching your git `user.name` / `user.email`, writes `~/.local/state/omarchy/garden/heatmap.json`.

`~/Projects` is empty until you clone code there; vaults under `~/Documents` already fill squares.
