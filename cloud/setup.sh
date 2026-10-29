#!/usr/bin/env bash
# One-time setup in a cloud session (repo root): libraries, then the Databento bars.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m pip install -q -r cloud/requirements.txt
python3 -m cloud.data
