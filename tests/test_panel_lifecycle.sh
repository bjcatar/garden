#!/usr/bin/env bash
# Loads the real plugin and PluginBarApi; no popup surfaces are mapped.
set -euo pipefail
repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
shell_dir=${OMARCHY_PATH:-/usr/share/omarchy}/shell
test_dir=$(mktemp -d /tmp/garden-lifecycle.XXXXXX)
trap 'rm -rf -- "$test_dir"' EXIT
ln -s "$shell_dir/Commons" "$test_dir/Commons"
ln -s "$shell_dir/Ui" "$test_dir/Ui"
ln -s "$repo_dir" "$test_dir/garden"
cp "$repo_dir/tests/qml/panel-lifecycle.qml" "$test_dir/shell.qml"
QT_QPA_PLATFORM=wayland timeout 10s quickshell -p "$test_dir" --no-color > "$test_dir/output" 2>&1
cat "$test_dir/output"
rg -q GARDEN_TEST_PASS "$test_dir/output"
if rg -q 'GARDEN_TEST_FAIL|ERROR|WARN scene:' "$test_dir/output"; then
  exit 1
fi
