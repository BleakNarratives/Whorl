#!/data/data/com.termux/files/usr/bin/bash
# ─────────────────────────────────────────────────────
#  WHORL — Termux Install Script
#  Run from the whorl/ repo root:
#    bash scripts/install.sh
# ─────────────────────────────────────────────────────

set -e

echo ""
echo " Installing WHORL on Termux..."
echo ""

# Core deps
pip install --break-system-packages requests toml

# Optional: uncomment what you need
# pip install --break-system-packages feedparser        # scouts with RSS
# pip install --break-system-packages websockets        # nostr relay

# Install whorl itself in editable mode
pip install --break-system-packages -e .

echo ""
echo " Running DB migrations..."
whorl db migrate

echo ""
echo " WHORL installed. Run: whorl status"
echo ""
