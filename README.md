# Garden

A private year of **coding on this Omarchy machine**.

Not GitHub.com. Not the Agents token meter. A square is a **half-hour with a file change** in a folder you chose, or a git commit **you** authored (pale tile if git-only). Six commits without a save still add nothing to the headline. A blank day is sampled only when a successful file walk covered that day. Until then, the day stays unmarked.

## Install

```bash
omarchy plugin add https://github.com/bjcatar/garden.git --enable --section right --after omarchy.agents
python3 ~/.config/omarchy/plugins/bjcatar.garden/bin/garden-scan --install-timer
python3 ~/.config/omarchy/plugins/bjcatar.garden/bin/garden-scan
```

Click the sprout on the right of the bar (after Agents). That opens **Year**, then scans once the shell releases its initial keyboard grab. **This week** is one tap away. On **This week**, **Copy Markdown** and the `c` key copy a Markdown week note. The box names the week range, days, projects, and recent commits in that note. Hours stay on the headline. The control reads Copied for a moment. A Garden notification says to paste the note into Obsidian. The note has a blank Note section to fill in after you paste. Garden does not save a file. **Projects** lists where you left off. **Year** is the heatmap. Click a day for a 48-slot strip and which repos lit each half-hour. Flick left for earlier months. A project shows time ranges. Those ranges overlap, so they are not added into the machine total. Use **Refresh** in the panel if you want another scan right now. **Enable background scan** if the 15-minute timer is off.

Escape closes the popup, including while editing a folder. Clicking the sprout again or outside the card also closes it. The folder field takes keyboard focus when clicked.

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

One themed Nerd Font sprout, same slot as Bluetooth. Hover is the sampled half-hours on this machine today. Left-click scans (if it has been more than 30s) and opens the year. Middle-click scans even if the panel is already open.

## Folders

Default watch: `~/Projects`. Open **Settings** on the panel to add or remove a folder, mute a project, and read the Garden version. The field accepts `~/Projects` and `$HOME/Projects`. Your home directory itself is rejected. Settings lists the folders in your home when nothing valid is watched, and when the path you typed is your home. `~/Documents` is not watched by default (vault backup crons).

**A folder does not need to be a git repo.** Nested git repos still count commits. Build and dependency folders are skipped by the scanner. They are not mutes.

## What lights a square

| Signal | Lights a 30-minute slot |
|---|---|
| File save | Source-ish files under a watched folder (skip `node_modules`, `.git`, venvs, …). Counted from **mtime samples**, not each keystroke. Untracked files in a git repo count if git would not ignore them. |
| Git commit | Author email matches yours, local time, subject not `vault backup:`. **Pushed commits still count.** |

**Sampled half-hours.** The headline counts half-hours with a file change on this PC. Git-only history lights pale tiles and adds nothing to the headline. Settings shows the last successful file walk, and whether the timer unit is enabled.

Agent token totals are **not** squares and are not shown in the panel.

## Data (all on this PC)

| Path | What |
|---|---|
| `~/.local/state/omarchy/garden/heatmap.json` | Derived calendar (widget reads this) |
| `~/.local/state/omarchy/garden/settings.json` | Roots, mutes, emails |
| `~/.local/state/omarchy/garden/ledger.jsonl` | File, git, and agent events |
| `~/.local/state/omarchy/garden/state.json` | File-walk windows and the last scan |
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

## Popup regression check

Run `bash tests/test_panel_lifecycle.sh` in an Omarchy Wayland session. It loads
the real Garden panel and `PluginBarApi` in a separate Quickshell process while
holding popup surfaces closed. It checks open, toggle, key-catcher and outside-click
close routes, and dismissal when the bar setter throws. It does not simulate
physical keyboard or pointer input.

## Maintainers

Release and marketplace update steps are in [Publish Garden](docs/PUBLISH.md).
