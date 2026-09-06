# Garden

A private year of **coding on this Omarchy machine**.

Not GitHub.com. Not the Agents token meter. A square is a half-hour when something actually changed in a folder you chose — a file save in a watched git repo, or a git commit **you** authored. Empty tiles are the bed, not a score. Days before Garden started watching are not a fake empty GitHub year of “you did nothing.”

This is **0.2.0**. First-run timer install and non-git folders land in later waves.

## Install

Until the public GitHub repo exists, from a checkout of this tree:

```bash
rsync -a --delete --exclude .git --exclude .hermes --exclude extras --exclude tests --exclude __pycache__ \
  ./ ~/.config/omarchy/plugins/bjcatar.garden/
omarchy plugin validate ~/.config/omarchy/plugins/bjcatar.garden
omarchy plugin enable bjcatar.garden --section right --after omarchy.agents
mkdir -p ~/.config/systemd/user
cp ~/.config/omarchy/plugins/bjcatar.garden/systemd/garden-scan.service \
   ~/.config/omarchy/plugins/bjcatar.garden/systemd/garden-scan.timer \
   ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now garden-scan.timer
python3 ~/.config/omarchy/plugins/bjcatar.garden/bin/garden-scan
omarchy-shell shell rescanPlugins
```

Then click the sprout on the right of the bar (after Agents). The year should open on **today**. Flick left for earlier months. Middle-click the sprout (or `r` in the panel) to scan now.

Later, when `https://github.com/bjcatar/garden` is public:

```bash
omarchy plugin add https://github.com/bjcatar/garden.git --enable --section right --after omarchy.agents
```

Then copy the systemd units as above (a `--install-timer` flag is not in this version yet).

## Bar

One themed Nerd Font sprout, same slot as Bluetooth. Hover is hours built **here** today. Left-click opens the year. Middle-click refreshes.

## Folders

Default watch: `~/Projects`. Add/remove folders in the panel. `$HOME` is rejected. `~/Documents` is not watched by default (vault backup crons).

**Today’s scanner only discovers git repos** under those folders. Untracked files and non-git directories are not counted yet.

## What lights a square (today)

| Signal | Lights a 30-minute slot |
|---|---|
| File save | Tracked files (`git ls-files`) in a watched repo |
| Git commit | Author email matches yours, local time, subject not `vault backup:` |

Agent token totals are **not** squares. The panel may show a one-line “most used model” from Omarchy’s existing agent usage files — that is tokens, not hours.

## Data (all on this PC)

| Path | What |
|---|---|
| `~/.local/state/omarchy/garden/heatmap.json` | Derived calendar (widget reads this) |
| `~/.local/state/omarchy/garden/settings.json` | Roots, mutes, emails |
| `~/.local/state/omarchy/garden/ledger.jsonl` | Observed events |
| `~/.config/systemd/user/garden-scan.{service,timer}` | Optional 15-minute scan |

## Uninstall

```bash
omarchy plugin disable bjcatar.garden
omarchy plugin remove bjcatar.garden
systemctl --user disable --now garden-scan.timer
rm -f ~/.config/systemd/user/garden-scan.service ~/.config/systemd/user/garden-scan.timer
systemctl --user daemon-reload
rm -rf ~/.local/state/omarchy/garden
```

## License

MIT
