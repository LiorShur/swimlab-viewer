#!/usr/bin/env bash
# Vendor the swimlab engine into ./vendor so the Cloud Function runtime (deploy
# and emulator) can import it. Run before `firebase deploy` / `firebase emulators`.
#
#   ./vendor_swimlab.sh /path/to/swimlab        # or set $SWIMLAB
set -euo pipefail
SWIMLAB="${1:-${SWIMLAB:-}}"
if [[ -z "${SWIMLAB}" || ! -d "${SWIMLAB}/swimlab" ]]; then
  echo "usage: $0 /path/to/swimlab  (the engine repo containing swimlab/ and config.yaml)" >&2
  exit 1
fi
DEST="$(cd "$(dirname "$0")" && pwd)/vendor"
rm -rf "${DEST}"; mkdir -p "${DEST}"
cp -r "${SWIMLAB}/swimlab" "${DEST}/swimlab"
cp "${SWIMLAB}/config.yaml" "${DEST}/config.yaml"
echo "vendored swimlab -> ${DEST} (config.yaml at ${DEST}/config.yaml)"
