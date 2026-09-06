# Garden

A private year of **coding on this Omarchy machine**.

Not GitHub.com. Not the Agents token meter. A square is a **half-hour you showed up** in a folder you chose — a file save, or a git commit **you** authored (including ones you already pushed). Six commits in the same window still light **one** square (0.5h). Empty tiles are the bed, not a score.

## Install

```bash
omarchy plugin add https://github.com/bjcatar/garden.git --enable --section right --after omarchy.agents
python3 ~/.config/omarchy/plugins/bjcatar.garden/bin/garden-scan --install-timer
python3 ~/.config/omarchy/plugins/bjcatar.garden/bin/garden-scan
```

Click the sprout on the right of the bar (after Agents). That **scans**, then opens the year on **today**. Click a day for a 48-slot strip and which repos lit each half-hour. Flick left for earlier months. Use **Refresh** in the panel if you want another scan right now. **Enable background scan** if the 15-minute timer is off.

`--install-timer` copies the user systemd units and enables a 15-minute scan while the panel is closed. Opening the panel (or Refresh) scans now. No per-monitor QML timer. The timer assumes the plugin lives at `~/.config/omarchy/plugins/bjcatar.garden`.

From a local checkout instead of GitHub:

```bash
rsync -a --delete --exclude .git --exclude .hermes --exclude extras --exclude tests --exclude __pycache__ \
  ./ ~/.config/omarchy/plugins/bjcatar.garden/
omarchy plugin validate ~/.config/omarchy/plugins/bjcatar.garden
omarchy plugin enable bjcatar.garden --section right --after omarchy.agents
python3 ~/.config/omarchy/plugins/bjcatar.garden/bin/garden-scan --install-timer
python3 ~/.config/omarchy/plugins/bjcatar.garden/bin/garden-scan
omarchy-shell shell rescanPlugins
```

## Bar

One themed Nerd Font sprout, same slot as Bluetooth. Hover is hours built **here** today. Left-click scans (if it has been more than 30s) and opens the year. Middle-click scans even if the panel is already open.

## Folders

Default watch: `~/Projects`. Add/remove folders in the panel. `$HOME` is rejected. `~/Documents` is not watched by default (vault backup crons).

**A folder does not need to be a git repo.** Nested git repos still count commits.

## What lights a square

| Signal | Lights a 30-minute slot |
|---|---|
| File save | Source-ish files under a watched folder (skip `node_modules`, `.git`, venvs, …). Counted from **mtime samples**, not each keystroke. Untracked files in a git repo count if git would not ignore them. |
| Git commit | Author email matches yours, local time, subject not `vault backup:`. **Pushed commits still count.** |

**Hours ≠ commit count.** The headline counts lit half-hours, not how many times you saved.

Agent token totals are **not** squares and are not shown in the panel.

## Data (all on this PC)

| Path | What |
|---|---|
| `~/.local/state/omarchy/garden/heatmap.json` | Derived calendar (widget reads this) |
| `~/.local/state/omarchy/garden/settings.json` | Roots, mutes, emails |
| `~/.local/state/omarchy/garden/ledger.jsonl` | Observed events |
| `~/.config/systemd/user/garden-scan.{service,timer}` | 15-minute scan (from `--install-timer`) |

## Uninstall

```bash
python3 ~/.config/omarchy/plugins/bjcatar.garden/bin/garden-scan --uninstall-timer
omarchy plugin disable bjcatar.garden
omarchy plugin remove bjcatar.garden
rm -rf ~/.local/state/omarchy/garden
```

If the plugin directory is already gone:

```bash
systemctl --user disable --now garden-scan.timer
rm -f ~/.config/systemd/user/garden-scan.service ~/.config/systemd/user/garden-scan.timer
systemctl --user daemon-reload
```

## License

MIT
