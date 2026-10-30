#!/usr/bin/env bash
set -euo pipefail
if [[ "$(uname -s)" != "Darwin" ]]; then
  echo 'Run this installer on the Mac with Futu OpenD.'
  exit 1
fi
python3 -c 'import sys; assert sys.version_info >= (3, 9), "Python 3.9 or newer is required"'
connector_root="$HOME/.local/share/tradeagent-hk-futu"
mkdir -p "$connector_root"
chmod 700 "$connector_root"
python3 -m venv "$connector_root/venv"
"$connector_root/venv/bin/python" -m pip install 'futu-api>=9.3,<11' 'requests>=2.32,<3'
cp "$(dirname "$0")/futu_lookup_connector.py" "$connector_root/connector.py"
echo 'In the dashboard, sign in as lewisf and choose Pair Mac connector.'
echo 'Keep OpenD signed in and this terminal open. No incoming network port is opened.'
exec "$connector_root/venv/bin/python" "$connector_root/connector.py" "$@"
