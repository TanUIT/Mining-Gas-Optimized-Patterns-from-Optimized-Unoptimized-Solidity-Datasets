#!/usr/bin/env bash
# Idempotent Cloud Agent install for the Solidity gas-pattern-mining pipeline.
# Provisions:
#   - Solidity compiler (solc) managed via solc-select
#   - Foundry toolkit (forge/cast/anvil/chisel) for gas reports
#   - Python project dependencies (system-wide, so `python3 -m gasmine` works)
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

SOLC_VERSION="${SOLC_VERSION:-0.8.30}"
SOLTOOLS_VENV="$HOME/.venvs/soltools"

# 1) System packages: python venv support (for the isolated solc-select venv).
if ! dpkg -s python3.12-venv >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo apt-get install -y -qq python3.12-venv
fi

# 2) solc-select in an isolated venv, exposed on the always-on-PATH /usr/local/bin.
if [ ! -x "$SOLTOOLS_VENV/bin/python" ]; then
  python3 -m venv "$SOLTOOLS_VENV"
fi
"$SOLTOOLS_VENV/bin/pip" install --upgrade pip >/dev/null
"$SOLTOOLS_VENV/bin/pip" install --upgrade solc-select >/dev/null
sudo ln -sf "$SOLTOOLS_VENV/bin/solc-select" /usr/local/bin/solc-select
sudo ln -sf "$SOLTOOLS_VENV/bin/solc" /usr/local/bin/solc

# 3) Install & select the solc version (safe to re-run).
if ! solc-select versions 2>/dev/null | grep -q "^${SOLC_VERSION}"; then
  solc-select install "$SOLC_VERSION"
fi
solc-select use "$SOLC_VERSION"

# 4) Foundry toolkit for compiling contracts and producing gas reports.
if [ ! -x "$HOME/.foundry/bin/forge" ]; then
  curl -L https://foundry.paradigm.xyz | bash
fi
"$HOME/.foundry/bin/foundryup"
for b in forge cast anvil chisel; do
  [ -x "$HOME/.foundry/bin/$b" ] && sudo ln -sf "$HOME/.foundry/bin/$b" /usr/local/bin/"$b"
done

# 5) Python project dependencies, installed for the system interpreter so that
#    `python3 -m gasmine ...` works without activating a virtualenv (this is an
#    ephemeral container, so --break-system-packages is appropriate here).
if [ -f requirements.txt ]; then
  python3 -m pip install --break-system-packages --upgrade pip >/dev/null 2>&1 || true
  python3 -m pip install --break-system-packages -r requirements.txt
fi

echo "install complete: $(solc --version | tail -1) | $(forge --version | head -1)"
