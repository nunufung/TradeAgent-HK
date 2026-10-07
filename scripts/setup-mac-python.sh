#!/usr/bin/env bash
# Use an installed interpreter; installing macOS Python in CI can require sudo.
set -euo pipefail

minimum_minor="${TAHK_PYTHON_MIN_MINOR:-11}"
[[ "$minimum_minor" =~ ^[0-9]+$ ]] || { echo "Invalid minimum Python version." >&2; exit 1; }

compatible_python() {
  [ -x "$1" ] && "$1" -c 'import sys; sys.exit(0 if sys.version_info.major == 3 and sys.version_info.minor >= int(sys.argv[1]) else 1)' "$minimum_minor" 2>/dev/null
}

selected_python=""
if [ -n "${TAHK_MAC_PYTHON:-}" ]; then
  if ! compatible_python "$TAHK_MAC_PYTHON"; then
    echo "TAHK_MAC_PYTHON must point to an executable Python 3.${minimum_minor} or newer." >&2
    exit 1
  fi
  selected_python="$TAHK_MAC_PYTHON"
else
  candidates=("$HOME/tradeagent-futu-test/bin/python")
  for version in 3.11 3.12 3.13 3.14; do
    candidates+=(
      "/opt/homebrew/bin/python${version}"
      "/opt/homebrew/opt/python@${version}/bin/python${version}"
      "/usr/local/bin/python${version}"
      "/usr/local/opt/python@${version}/bin/python${version}"
      "/Library/Frameworks/Python.framework/Versions/${version}/bin/python${version}"
    )
  done
  candidates+=("/opt/homebrew/bin/python3" "/usr/local/bin/python3")
  if command -v python3 >/dev/null 2>&1; then
    candidates+=("$(command -v python3)")
  fi
  for candidate in "${candidates[@]}"; do
    if compatible_python "$candidate"; then
      selected_python="$candidate"
      break
    fi
  done
fi

if [ -z "$selected_python" ]; then
  echo "No installed Python 3.${minimum_minor} or newer was found on this Mac." >&2
  echo "Install Python 3.11 once in Mac Terminal or set repository variable TAHK_MAC_PYTHON to an installed interpreter's absolute path. Then start a new workflow run." >&2
  exit 1
fi

: "${RUNNER_TEMP:?Runner temporary directory is required}"
: "${GITHUB_PATH:?GitHub path file is required}"
: "${GITHUB_ENV:?GitHub environment file is required}"
venv_dir="$(mktemp -d "$RUNNER_TEMP/tradeagent-python.XXXXXX")"
"$selected_python" -m venv "$venv_dir"
"$venv_dir/bin/python" -c 'import sys; print("Local Python ready:", sys.version.split()[0])'
"$venv_dir/bin/python" -m pip --version
printf '%s\n' "$venv_dir/bin" >> "$GITHUB_PATH"
printf 'VIRTUAL_ENV=%s\n' "$venv_dir" >> "$GITHUB_ENV"
