from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "marketplace-update-body.sh"
EXAMPLE_SHA = "0123456789abcdef0123456789abcdef01234567"
HEADINGS = [
    "Verification action",
    "Plugin ID",
    "Repository URL",
    "Target commit",
    "Verification acknowledgment",
    "Standard installation acknowledgment",
]
ACK = (
    "- [x] I understand that only the exact target commit can become a "
    "verified marketplace snapshot and that verification is not a security audit."
)


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def expected_body(sha: str) -> str:
    sections = [
        ("Verification action", "Verify and publish a newer upstream commit"),
        ("Plugin ID", "bjcatar.garden"),
        ("Repository URL", "https://github.com/bjcatar/garden"),
        ("Target commit", sha),
        ("Verification acknowledgment", ACK),
        ("Standard installation acknowledgment", "_No response_"),
    ]
    parts = [f"### {heading}\n\n{body}" for heading, body in sections]
    return "\n\n".join(parts) + "\n"


class MarketplaceBodyTests(unittest.TestCase):
    def test_example_sha_prints_six_sections(self):
        proc = run(EXAMPLE_SHA)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, expected_body(EXAMPLE_SHA))
        headings = [
            line[4:] for line in proc.stdout.splitlines() if line.startswith("### ")
        ]
        self.assertEqual(headings, HEADINGS)

    def test_router_sees_the_update_action(self):
        proc = run(EXAMPLE_SHA)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertRegex(
            proc.stdout,
            r"^### Verification action\n\nVerify and publish a newer upstream commit\n",
        )

    def test_short_sha_prints_nothing(self):
        proc = run("abc1234")
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, "")

    def test_uppercase_sha_is_stored_in_lowercase(self):
        proc = run(EXAMPLE_SHA.upper())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, expected_body(EXAMPLE_SHA))

    def test_default_sha_is_head(self):
        head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
        proc = run()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, expected_body(head))

    def test_title_uses_the_commit_manifest(self):
        head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
        raw = subprocess.check_output(
            ["git", "show", f"{head}:manifest.json"], cwd=ROOT, text=True
        )
        manifest = json.loads(raw)
        proc = run("--title", head)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(
            proc.stdout,
            f"[Verify]: {manifest['name']} {manifest['version']} \u2014 publish {head[:7]}\n",
        )

    def test_script_does_not_name_service_control(self):
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("systemctl", text)
        self.assertNotIn("systemd-run", text)

    def test_workflow_calls_the_script_and_does_not_embed_the_form(self):
        text = (ROOT / ".github/workflows/release-marketplace.yml").read_text(
            encoding="utf-8"
        )
        for banned in (
            "### Verification action",
            "Verify and publish a newer upstream commit",
            "I understand that only the exact target commit",
            "_No response_",
            "https://github.com/bjcatar/garden",
        ):
            self.assertNotIn(banned, text, banned)
        for required in (
            "open_marketplace_issue",
            "default: false",
            "MARKETPLACE_ISSUE_TOKEN",
            "python3 -m unittest discover -s tests -q",
            "tests/test_panel_lifecycle.sh",
            "types: [published]",
            "github.event_name == 'workflow_dispatch' && inputs.open_marketplace_issue == true",
            "bash scripts/marketplace-update-body.sh",
        ):
            self.assertIn(required, text, required)

    def test_runbook_fence_matches_the_script(self):
        text = (ROOT / "docs/PUBLISH.md").read_text(encoding="utf-8")
        marker = "```text\n### Verification action\n"
        start = text.index(marker) + len("```text\n")
        end = text.index("\n```", start)
        fenced = text[start:end] + "\n"
        proc = run(EXAMPLE_SHA)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(fenced, proc.stdout)
        self.assertIn("docs/PUBLISH.md", (ROOT / "README.md").read_text(encoding="utf-8"))
