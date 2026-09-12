#!/usr/bin/env bash
# Download and pin an Open-MBEE/sysml-toolkit release binary by tag,
# verifying its sha256 against a recorded digest.
#
# No PyPI wheel exists for this tool (the `sysmlv2` PyPI name is an
# unrelated placeholder from a different party) -- this is the real,
# supported pinning path.
#
# Usage:
#   TAG=v0.6.0 [PLATFORM=aarch64-apple-darwin] [EXPECTED_SHA256=<hex>] \
#   toolchain/get-sysml-toolkit.sh

set -euo pipefail

: "${TAG:?set TAG, e.g. v0.6.0}"
PLATFORM="${PLATFORM:-aarch64-apple-darwin}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/.cache/sysml-toolkit/$TAG"
mkdir -p "$OUT"

ASSET="sysmlv2-${TAG#v}-${PLATFORM}.tar.gz"
URL="https://github.com/Open-MBEE/sysml-toolkit/releases/download/${TAG}/${ASSET}"

echo "== downloading $URL ==" >&2
curl -fL -o "$OUT/$ASSET" "$URL"
tar xzf "$OUT/$ASSET" -C "$OUT"
BIN="$OUT/sysmlv2"
chmod +x "$BIN"

ACTUAL=$(shasum -a 256 "$BIN" | awk '{print $1}')
echo "sha256: $ACTUAL (record as the Version's svt:artifactDigest)" >&2
if [ -n "${EXPECTED_SHA256:-}" ] && [ "$ACTUAL" != "$EXPECTED_SHA256" ]; then
	echo "error: sha256 mismatch: expected $EXPECTED_SHA256, got $ACTUAL" >&2
	exit 1
fi

echo "export SYSMLV2_BIN=\"$BIN\""
