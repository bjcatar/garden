# Publish Garden

Garden is already listed on the Omarchy marketplace as `bjcatar.garden`. Use this page to cut a release and ask marketplace maintainers to verify a newer commit.

The workflow prepares the issue body. A manual run opens the marketplace issue only when you set `open_marketplace_issue`. Publishing a GitHub Release leaves the issue unopened.

If this page and the upstream docs disagree, follow the upstream docs and update this page.

- [Submit a plugin](https://github.com/omacom/omarchy-plugin-marketplace/blob/main/SUBMISSION.md) is the listing guide. Garden already completed that form.
- [Plugin verification](https://github.com/omacom/omarchy-plugin-marketplace/blob/main/VERIFICATION.md) defines snapshot status and the update path.
- [Plugin verification form](https://github.com/omacom/omarchy-plugin-marketplace/issues/new?template=verify-plugin.yml) is the issue you open for an update.

## Check the tree

Confirm the repository still meets the marketplace structure checks.

- The GitHub repository is public. Use `https://github.com/bjcatar/garden` with no trailing slash.
- `manifest.json` is in the repository root. The id is `bjcatar.garden`. That id stays, and it sits outside the reserved `omarchy.*` namespace.
- `README.md` contains installation and removal instructions. In this repo those are Install and Uninstall.
- `LICENSE` is in the repository root.
- A root preview is optional. This repo ships `preview.png`. The marketplace also accepts `preview.jpg`, `preview.jpeg`, `preview.webp`, and `preview.avif`. The file must be at most 50 MB and 40 megapixels. The marketplace discards the original and generates the card and detail images.

## Verify on your machine

1. Run the Python tests.

   ```bash
   python3 -m unittest discover -s tests -q
   ```

2. On an Omarchy Wayland session, run the panel lifecycle test.

   ```bash
   bash tests/test_panel_lifecycle.sh
   ```

   The test needs quickshell. It loads the real panel and checks open, toggle, key-catcher close, outside-click close, and close when the bar setter throws. It does not press a physical key. CI does not run it. The GitHub runner has no Omarchy session.

3. Install this checkout with the rsync block in the README Install section. That block runs `omarchy plugin validate` and `omarchy-shell shell rescanPlugins`.

4. Restart the shell.

   ```bash
   omarchy restart shell
   ```

5. Click the sprout. Close the panel with Escape. Open it and close it by clicking outside the card. Open it and close it by clicking the sprout again.

## Set the version

Edit `version` in `manifest.json`. Leave the `v` prefix off. The git tag is `v` plus that version. `v0.2.4` matches manifest `0.2.4`.

Put the release notes on the GitHub Release. This repo has no changelog file. Do not add one for a normal release.

Do not bump the version when the only change is this runbook.

## Cut the release

1. Put the version change on a branch and open a pull request.
2. Merge it to `main`.
3. Tag that commit and push the tag. The commit must contain `scripts/marketplace-update-body.sh`. The workflow checks out the tag and runs the script from that commit.

   ```bash
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```

4. Publish a GitHub Release for the tag. The release notes are the changelog.

Publishing the release starts `.github/workflows/release-marketplace.yml`. The job checks out the tag, checks the manifest, README, license, and preview, runs the Python tests, and uploads `marketplace-issue`. That artifact holds `title.txt` and `body.md`. The same text is in the job summary. The job does not open an issue.

A tag that does not match `v` plus the manifest version fails the job. A preview larger than 50 MB or 40 megapixels fails the job. The size check accepts the current `preview.png`. The picture is from before the three panel views, so replace it before you ask the marketplace to publish the commit. The check accepts any PNG inside those limits.

## Request a marketplace update

On the [Plugin verification form](https://github.com/omacom/omarchy-plugin-marketplace/issues/new?template=verify-plugin.yml), choose **Verify and publish a newer upstream commit**.

You can paste the script output instead of using the form controls. Print the title, then the body.

```bash
bash scripts/marketplace-update-body.sh --title
bash scripts/marketplace-update-body.sh
```

With no argument the script uses `git rev-parse HEAD`. Pass one full 40-character SHA to target that commit. `--title` reads `name` and `version` from that commit's `manifest.json`. An uncommitted version edit does not change the title.

The body has six headings, in this order, and no seventh heading. A blank line follows each heading. The marketplace router requires the blank line under `Verification action`. Without that blank line, the issue is handled as a check of the commit already listed.

The first listing used the submission form, including category and tags. Do not send that form again.

Do not add a Maintainer notes heading. Any extra `###` heading makes the parser reject the issue.

The acknowledgment stays checked, and the words stay exact. Leave standard installation as `_No response_`. That section has to be present. Use the checked standard-installation box only when you are asking maintainers to drop a manual-install override. Garden's update does not ask for that.

The script prints this body for `0123456789abcdef0123456789abcdef01234567`.

```text
### Verification action

Verify and publish a newer upstream commit

### Plugin ID

bjcatar.garden

### Repository URL

https://github.com/bjcatar/garden

### Target commit

0123456789abcdef0123456789abcdef01234567

### Verification acknowledgment

- [x] I understand that only the exact target commit can become a verified marketplace snapshot and that verification is not a security audit.

### Standard installation acknowledgment

_No response_
```

Regenerate the body for the real commit. Do not file the example SHA.

The marketplace rejects a request whose commit is already the listed snapshot. Garden 0.2.3 was listed from `3e9d56ba47db1f6cbf353b76291ecef5c515f34a`. Check the plugin page for the live snapshot before you file. Leave that SHA out of the script. The marketplace rejects the listed commit on its own.

The baseline flags systemd unit files and `systemctl` as the `service-management` capability. The scan still sees that capability in the unit files, in `bin/garden-scan`, and in the README uninstall section. Expect `review-required` again. A marketplace maintainer has to accept that capability for the new commit. Deleting words from this page leaves the scan result unchanged.

To open the issue from Actions, run this workflow with **Run workflow**. Set `tag`, `sha`, or both. When both are set, they must be the same commit, and the tag must look like `vX.Y.Z`. Set `open_marketplace_issue` to true only when you want the issue opened. The default is false.

That step needs the Actions secret `MARKETPLACE_ISSUE_TOKEN` on this repository. Use a personal access token that can create issues on `omacom/omarchy-plugin-marketplace`. The workflow sets `GH_TOKEN` to that secret for the open step only. The default `GITHUB_TOKEN` cannot create issues in that repository. If the secret is missing, the open step fails and no issue is created. The artifact from the earlier step remains.

If an issue with the same title already exists, the step stops and prints its URL. It does not edit that issue. The search looks at 100 titles. If you do not see the one you expect, look on the marketplace repo before you run the step again.

## After the issue is open

Opening the issue runs compatibility validation and the Automated Security Baseline on that exact commit. The baseline reads the commit and does not execute plugin code. The listed snapshot stays in place while the update is pending.

`approved-and-verified` is a label a marketplace maintainer applies after the bot comments, and only as the last label. This repository cannot apply it. A `passed` scan with no findings can verify on its own. `service-management` is `review-required`, so the maintainer has to accept the reported capability set. Findings the baseline treats as blocking stop the update until a new commit fixes them.

The catalog keeps the previous snapshot until publication finishes. A newer commit on `main` shows as an unverified update until then. `omarchy plugin add` and `omarchy plugin update` clone the mutable branch head, so the installed commit can differ from the verified snapshot.

## Replace the preview

`preview.png` is a PNG, 1280 by 780, 99638 bytes. Its sha256 is `bb54edab720cc0093ba2f2996b7355a8c75ab49be762332b136e9dceb635c9ee`. That file predates the **Year**, **This week**, and **Projects** switcher in `Panel.qml`. Capture a new preview on Omarchy before the next marketplace update. Do not commit a drawn stand-in.

The marketplace reads one root preview. Put the open panel on **Year** in `preview.png`. A sprout click opens **Year**.

These frames are optional.

- The bar sprout in its slot.
- The panel on **This week**.
- The panel on **Projects**.

1. Install the commit you will tag, using the rsync block in the README.
2. Run `omarchy restart shell`.
3. Open the panel and select the view you are capturing.
4. Capture the region.

   ```bash
   grim -g "$(slurp)" preview.png
   ```

   Spectacle can write the same file.

   ```bash
   spectacle -r -b -o preview.png
   ```

5. Read the size. It must be at most 50 MB and 40 megapixels. You do not have to resize it to 1280 by 780.

   ```bash
   python3 - <<'PY'
   import struct
   from pathlib import Path
   data = Path("preview.png").read_bytes()
   width, height = struct.unpack(">II", data[16:24])
   print(f"{width}x{height} {len(data)} bytes {width * height / 1e6:.2f} megapixels")
   PY
   ```

6. Confirm `sha256sum preview.png` differs from the digest above, then commit `preview.png` with the release.
