# Garden

A private year of **coding on this Omarchy machine**.

Not GitHub.com. Not the Agents token meter. A square is a **half-hour with a file change** in a folder you chose, or a git commit **you** authored (pale tile if git-only). Six commits without a save still add nothing to the headline. A blank day is sampled only when a successful file walk covered that day. Until then, the day stays unmarked.

## Install

```bash
omarchy plugin add https://github.com/bjcatar/garden.git --enable --section right --after omarchy.agents
python3 ~/.config/omarchy/plugins/bjcatar.garden/bin/garden-scan --install-timer
python3 ~/.config/omarchy/plugins/bjcatar.garden/bin/garden-scan
```

Click the sprout on the right of the bar (after Agents). That opens **Year**, then scans once the shell releases its initial keyboard grab. **This week** is one tap away. On **This week**, **Copy Markdown** and the `c` key copy a Markdown week note. The box names the week range, days, projects, and recent commits in that note. Hours stay on the headline. The control reads Copied for a moment. A Garden notification says to paste the note into your notes. The note has a blank Note section to fill in after you paste. Garden does not save a file. **Projects** lists where you left off. **Year** is the heatmap. Click a day for a 48-slot strip and which repos lit each half-hour. Flick left for earlier months. A project shows time ranges. Those ranges overlap, so they are not added into the machine total. Use **Refresh** in the panel if you want another scan right now. **Enable background scan** if the 15-minute timer is off.

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

## Agent shell

Garden registers the IPC target `bjcatar.garden` with `IpcHandler` from `Quickshell.Io`, the same type the clock uses. The running shell answers on its own socket.

```bash
omarchy-shell bjcatar.garden toggle
omarchy-shell bjcatar.garden call
omarchy-shell bjcatar.garden resume
omarchy-shell bjcatar.garden open
omarchy-shell bjcatar.garden close
omarchy-shell shell toggle bjcatar.garden
```

`omarchy shell` runs `omarchy-shell`, so `omarchy shell shell toggle bjcatar.garden` is the same toggle. The second `shell` is the IPC target. `omarchy shell toggle bjcatar.garden` does not reach Garden.

`shell toggle` opens the panel on the focused screen, and closes it when that panel is already open. That path uses the bar widget's `open`, `close`, and `opened` properties. `bjcatar.garden toggle` calls the same functions on the widget instance that registered the target.

`call` prints the week note from the last scan, the same Markdown as **Copy Markdown**. `resume` prints the same handoff as `garden-scan --resume-md` and as **Copy resume for agent**. Before a scan has written `heatmap.json`, both commands print nothing and exit 0.

On **This week** and **Projects**, **Copy resume for agent** copies that handoff through the Omarchy clipboard. It is a separate control from **Copy Markdown** and from the `c` key. The notification title is Garden. The body says to paste the resume into an agent. Escape still closes the panel, including while the Settings folder field is focused.

## Folders

Default watch: `~/Projects`. Open **Settings** on the panel to add or remove a folder, mute a project, and read the Garden version. The field accepts `~/Projects` and `$HOME/Projects`. Your home directory itself is rejected. Settings lists the folders in your home when nothing valid is watched, and when the path you typed is your home. `~/Documents` is not watched by default (vault backup crons).

**A folder does not need to be a git repo.** Nested git repos still count commits. Build and dependency folders are skipped by the scanner. They are not mutes.

## What lights a square

| Signal | Lights a 30-minute slot |
|---|---|
| File save | Source-ish files under a watched folder (skip `node_modules`, `.git`, venvs, …). Counted from **mtime samples**, not each keystroke. Untracked files in a git repo count if git would not ignore them. |
| Git commit | Author email matches yours, local time, subject not `vault backup:`. **Pushed commits still count.** |

**Sampled half-hours.** The headline counts half-hours with a file change on this PC. Git-only history lights pale tiles and adds nothing to the headline. Settings shows the last successful file walk, and whether the timer unit is enabled.

This week names the latest file in a run by its path. Projects name that path on the latest file save. A path is not an agent.

Agent token totals are **not** squares and are not shown in the panel.

## Data (all on this PC)

| Path | What |
|---|---|
| `~/.local/state/omarchy/garden/heatmap.json` | Derived calendar (widget reads this) |
| `~/.local/state/omarchy/garden/settings.json` | Roots, mutes, emails |
| `~/.local/state/omarchy/garden/ledger.jsonl` | File, git, and agent events |
| `~/.local/state/omarchy/garden/state.json` | File-walk windows and the last scan |
| `~/.local/state/omarchy/garden/this-week.md` | Week note from `garden-scan --write-week` |
| `~/.config/systemd/user/garden-scan.{service,timer}` | 15-minute scan (from `--install-timer`) |

## Agents

`garden-scan` can print this week without opening the panel. The week flags read `heatmap.json` when `generatedAt` is at most 15 minutes old. They scan first when that file is older or is not valid JSON. They do not scan when the file or the week note is missing. Add `--scan` to scan first. `--write-week` overwrites `this-week.md` in the garden state directory. It does not write an Obsidian vault.

```bash
python3 ~/.config/omarchy/plugins/bjcatar.garden/bin/garden-scan --week-md
python3 ~/.config/omarchy/plugins/bjcatar.garden/bin/garden-scan --week-json
python3 ~/.config/omarchy/plugins/bjcatar.garden/bin/garden-scan --resume-md
python3 ~/.config/omarchy/plugins/bjcatar.garden/bin/garden-scan --write-week
python3 ~/.config/omarchy/plugins/bjcatar.garden/bin/garden-scan --scan --resume-md
```

`--week-md` prints the same Markdown the panel copies. `--resume-md` is a shorter handoff for `omarchy agent prompt` or Cursor. `--week-json` repeats `machineHours` from the heatmap. It does not add project windows into that total.

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
