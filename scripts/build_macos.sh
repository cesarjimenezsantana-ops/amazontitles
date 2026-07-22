#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
APP_VERSION="${APP_VERSION:-1.1.1}"
BUILD_ARCH="$(uname -m)"
VENV_DIR="${PROJECT_DIR}/.build-venv"

cd "${PROJECT_DIR}"

if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
    python3 -m venv "${VENV_DIR}"
fi

"${VENV_DIR}/bin/python" -m pip install --upgrade pip
"${VENV_DIR}/bin/python" -m pip install -r requirements-build.txt
"${VENV_DIR}/bin/python" packaging/create_icons.py

APP_VERSION="${APP_VERSION}" "${VENV_DIR}/bin/pyinstaller" \
    --noconfirm \
    --clean \
    packaging/FocusAmazonTools.spec

APP_PATH="${PROJECT_DIR}/dist/Focus Amazon Tools.app"
if [[ ! -d "${APP_PATH}" ]]; then
    echo "The macOS application bundle was not created." >&2
    exit 1
fi

if [[ -n "${MACOS_SIGNING_IDENTITY:-}" ]]; then
    codesign --force --deep --options runtime --timestamp \
        --sign "${MACOS_SIGNING_IDENTITY}" "${APP_PATH}"
else
    codesign --force --deep --sign - "${APP_PATH}"
fi

STAGING_DIR="$(mktemp -d)"
trap 'rm -rf "${STAGING_DIR}"' EXIT
ditto "${APP_PATH}" "${STAGING_DIR}/Focus Amazon Tools.app"
ln -s /Applications "${STAGING_DIR}/Applications"

DMG_PATH="${PROJECT_DIR}/dist/FocusAmazonTools-${APP_VERSION}-macOS-${BUILD_ARCH}.dmg"
hdiutil create \
    -volname "Focus Amazon Tools" \
    -srcfolder "${STAGING_DIR}" \
    -ov \
    -format UDZO \
    "${DMG_PATH}"

if [[ -n "${MACOS_SIGNING_IDENTITY:-}" ]]; then
    codesign --force --timestamp --sign "${MACOS_SIGNING_IDENTITY}" "${DMG_PATH}"
fi

if [[ -n "${APPLE_ID:-}" && -n "${APPLE_TEAM_ID:-}" && -n "${APPLE_APP_PASSWORD:-}" ]]; then
    xcrun notarytool submit "${DMG_PATH}" \
        --apple-id "${APPLE_ID}" \
        --team-id "${APPLE_TEAM_ID}" \
        --password "${APPLE_APP_PASSWORD}" \
        --wait
    xcrun stapler staple "${DMG_PATH}"
fi

echo "Created ${DMG_PATH}"
