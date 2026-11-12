#!/bin/bash
set -euo pipefail
if [ "$#" -ne 1 ]; then
  echo 'Usage: bash export_ncnn.sh /path/to/new/candidate-directory' >&2
  exit 2
fi
python "$(dirname "$0")/export_ncnn.py" --output-root "$1"
