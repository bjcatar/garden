#!/usr/bin/env bash
set -euo pipefail

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
mode=body
sha=""

usage() {
  printf '%s\n' "Usage: scripts/marketplace-update-body.sh [--title] [SHA]" >&2
  exit 2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --title)
      mode=title
      shift
      ;;
    --help|-h)
      usage
      ;;
    --)
      shift
      break
      ;;
    -*)
      printf 'Unknown option: %s\n' "$1" >&2
      exit 2
      ;;
    *)
      if [[ -n "$sha" ]]; then
        printf '%s\n' "Pass one SHA." >&2
        exit 2
      fi
      sha=$1
      shift
      ;;
  esac
done

if [[ $# -gt 0 ]]; then
  printf '%s\n' "Pass one SHA." >&2
  exit 2
fi

if [[ -z "$sha" ]]; then
  sha=$(git -C "$root" rev-parse HEAD)
fi

sha=$(printf '%s' "$sha" | tr '[:upper:]' '[:lower:]')
if [[ ! "$sha" =~ ^[a-f0-9]{40}$ ]]; then
  printf '%s\n' "Pass a full 40-character SHA, or no argument to use HEAD." >&2
  exit 2
fi

if [[ "$mode" == "title" ]]; then
  manifest=$(git -C "$root" show "${sha}:manifest.json")
  name_version=$(printf '%s' "$manifest" | python3 -c '
import json, re, sys
manifest = json.load(sys.stdin)
if manifest.get("id") != "bjcatar.garden":
    raise SystemExit("manifest id is not bjcatar.garden")
name = manifest.get("name")
version = manifest.get("version")
if not isinstance(name, str) or name.strip() == "" or "\n" in name:
    raise SystemExit("manifest name is empty")
if not isinstance(version, str) or re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version) is None:
    raise SystemExit("manifest version is not X.Y.Z")
sys.stdout.write(name + "\n" + version + "\n")
')
  name=$(printf '%s\n' "$name_version" | sed -n '1p')
  version=$(printf '%s\n' "$name_version" | sed -n '2p')
  printf '[Verify]: %s %s \u2014 publish %s\n' "$name" "$version" "${sha:0:7}"
  exit 0
fi

cat <<EOF
### Verification action

Verify and publish a newer upstream commit

### Plugin ID

bjcatar.garden

### Repository URL

https://github.com/bjcatar/garden

### Target commit

${sha}

### Verification acknowledgment

- [x] I understand that only the exact target commit can become a verified marketplace snapshot and that verification is not a security audit.

### Standard installation acknowledgment

_No response_
EOF
