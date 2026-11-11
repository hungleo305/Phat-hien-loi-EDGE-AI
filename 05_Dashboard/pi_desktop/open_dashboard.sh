#!/bin/bash
set -euo pipefail
url=http://127.0.0.1:8768
systemctl --user start datn-station.service
for attempt in $(seq 1 60); do
  if /usr/bin/python3 -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8768/api/state", timeout=1).close()' 2>/dev/null; then
    if [[ "${1:-}" == "--check" ]]; then
      echo "Dashboard is reachable; motor was not started."
    else
      /usr/bin/chromium --new-window "$url" >/dev/null 2>&1 &
    fi
    exit 0
  fi
  sleep 1
done
message='Không mở được dashboard DATN. Kiểm tra dịch vụ datn-station.service.'
if command -v zenity >/dev/null; then
  zenity --error --title='Dashboard DATN' --text="$message"
else
  echo "$message" >&2
fi
exit 1
