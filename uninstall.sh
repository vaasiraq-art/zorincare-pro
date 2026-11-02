#!/usr/bin/env bash
set -euo pipefail

echo "Uninstalling ZorinCare Pro..."
sudo apt-get remove --purge -y zorincare-pro || true
echo "ZorinCare Pro has been removed. (Optional user settings/backups remain in ~/.config/zorincare-pro and ~/.local/share/zorincare-pro)"
