#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
python3 "$SCRIPT_DIR/build_deb.py"
echo "Done! Install on Zorin OS 18.1 Pro with:"
echo "  sudo apt install ./dist/zorincare-pro_1.0.0_all.deb"
