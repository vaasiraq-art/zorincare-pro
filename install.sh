#!/usr/bin/env bash
# ============================================================================
# ZorinCare Pro — 1-Click Installer for Zorin OS 18.1 Pro & Ubuntu 24.04 LTS
# ============================================================================
set -euo pipefail

echo "============================================================"
echo "  Installing ZorinCare Pro v1.0.0 for Zorin OS 18.1 Pro"
echo "============================================================"

if [[ "$(uname -s)" != "Linux" ]]; then
    echo "Error: install.sh must be executed on Zorin OS / Ubuntu Linux."
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-.}")" && pwd)"

if [[ ! -f "$SCRIPT_DIR/scripts/build_deb.py" ]]; then
    echo "[*] Downloading ZorinCare Pro source repository..."
    TMP_DIR="$(mktemp -d)"
    trap 'rm -rf "$TMP_DIR"' EXIT
    REPO_URL="${ZORINCARE_REPO_URL:-https://github.com/vaasiraq-art/zorincare-pro.git}"
    git clone --depth=1 "$REPO_URL" "$TMP_DIR/zorincare-pro"
    SCRIPT_DIR="$TMP_DIR/zorincare-pro"
fi

echo "[1/3] Installing required GTK4, Libadwaita & hardware management packages..."
sudo apt-get update -qq
sudo apt-get install -y \
    python3 \
    python3-gi \
    python3-gi-cairo \
    gir1.2-gtk-4.0 \
    gir1.2-adw-1 \
    ubuntu-drivers-common \
    fwupd \
    ufw \
    pciutils \
    usbutils

if ! command -v pkexec >/dev/null 2>&1; then
    sudo apt-get install -y pkexec || sudo apt-get install -y policykit-1
fi

echo "[2/3] Building ZorinCare Pro .deb package..."
python3 "$SCRIPT_DIR/scripts/build_deb.py"

DEB_FILE="$SCRIPT_DIR/dist/zorincare-pro_1.0.0_all.deb"
echo "[3/3] Installing $DEB_FILE..."
sudo dpkg -i "$DEB_FILE" || sudo apt-get install -f -y

echo ""
echo "============================================================"
echo "  ZorinCare Pro v1.0.0 installed successfully!"
echo "  Launch from Zorin Menu -> System Tools -> ZorinCare Pro"
echo "  Or run in terminal: zorincare-pro"
echo "============================================================"
