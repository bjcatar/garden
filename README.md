# Garden

What you actually did **on this PC**, in folders you chose.

Not GitHub.com. Not the Agents token meter. A square is a half-hour when a tracked file changed or you made a commit in a watched repo. Vault backup crons stay pale. History that only exists in git is labeled as such.

## Install

```bash
omarchy plugin add <this-repo-url> --enable --section right
systemctl --user enable --now garden-scan.timer
```

On this machine the live copy is `~/.config/omarchy/plugins/bjcatar.garden`. After editing the repo:

```bash
rsync -a --exclude .git --exclude .hermes --exclude extras --exclude __pycache__ \
  ~/Projects/personal/local-contrib/ ~/.config/omarchy/plugins/bjcatar.garden/
omarchy-shell shell rescanPlugins
python3 ~/.config/omarchy/plugins/bjcatar.garden/bin/garden-scan
```

## Bar

A **standard icon slot**: seven 2px ticks for the last week. Left-click opens the year. Middle-click / `r` refreshes.

## Folders

Default watch: `~/Projects` (not `~/Documents`). Add/remove folders in the panel. `$HOME` is rejected.

## Data

| Path | What |
|---|---|
| `~/.local/state/omarchy/garden/heatmap.json` | Derived calendar (widget reads this) |
| `~/.local/state/omarchy/garden/settings.json` | Roots, mutes, source toggles |
| `~/.local/state/omarchy/garden/ledger.jsonl` | Observed events |

Scanner is a systemd user timer every 15 minutes. The widget does **not** scan on its own (avoids two-monitor storms).

## Uninstall

```bash
omarchy plugin disable bjcatar.garden
omarchy plugin remove bjcatar.garden
systemctl --user disable --now garden-scan.timer
rm -rf ~/.local/state/omarchy/garden
```
