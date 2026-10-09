#!/usr/bin/env bash
set -euo pipefail

# scripts/update-agy.sh
# Checks for or applies updates to the Antigravity CLI (agy) pinned in Dockerfile.

MANIFEST_URL="https://antigravity-cli-auto-updater-974169037036.us-central1.run.app/manifests/linux_amd64.json"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKERFILE="${SCRIPT_DIR}/../Dockerfile"

if [[ ! -f "${DOCKERFILE}" ]]; then
  echo "Error: Dockerfile not found at ${DOCKERFILE}" >&2
  exit 1
fi

CHECK_MODE=false
if [[ "${1:-}" == "--check" ]]; then
  CHECK_MODE=true
fi

# Fetch manifest
MANIFEST_JSON=$(curl -fsSL --connect-timeout 15 --max-time 60 "${MANIFEST_URL}")
LATEST_VERSION=$(echo "${MANIFEST_JSON}" | jq -r '.version // empty')
LATEST_URL=$(echo "${MANIFEST_JSON}" | jq -r '.url // empty')
LATEST_SHA512=$(echo "${MANIFEST_JSON}" | jq -r '.sha512 // empty')

if [[ -z "${LATEST_VERSION}" || -z "${LATEST_URL}" || -z "${LATEST_SHA512}" ]]; then
  echo "Error: Failed to parse manifest from ${MANIFEST_URL}" >&2
  exit 1
fi

if [[ ! "${LATEST_VERSION}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Error: Invalid version format '${LATEST_VERSION}' in manifest" >&2
  exit 1
fi

if [[ ! "${LATEST_URL}" =~ ^https://storage\.googleapis\.com/ ]]; then
  echo "Error: Invalid URL origin '${LATEST_URL}', must start with https://storage.googleapis.com/" >&2
  exit 1
fi

if [[ ! "${LATEST_SHA512}" =~ ^[a-fA-F0-9]{128}$ ]]; then
  echo "Error: Invalid sha512 checksum format in manifest" >&2
  exit 1
fi

CURRENT_VERSION=$(grep -E '^ARG AGY_VERSION=' "${DOCKERFILE}" | cut -d'"' -f2)

echo "Current pinned version: ${CURRENT_VERSION}"
echo "Latest upstream version: ${LATEST_VERSION}"

if [[ "${CURRENT_VERSION}" == "${LATEST_VERSION}" ]]; then
  echo "Antigravity CLI is already up to date."
  exit 0
fi

if [[ "${CHECK_MODE}" == true ]]; then
  echo "Update available: ${CURRENT_VERSION} -> ${LATEST_VERSION}"
  exit 2
fi

echo "Updating Antigravity CLI to ${LATEST_VERSION}..."

TMP_DIR=$(mktemp -d /tmp/agy-update-XXXXXX)
trap 'rm -rf "${TMP_DIR}"' EXIT

ARCHIVE="${TMP_DIR}/agy.tar.gz"
curl -fsSL --connect-timeout 15 --max-time 60 "${LATEST_URL}" -o "${ARCHIVE}"

# Verify SHA512
ACTUAL_SHA512=$(sha512sum "${ARCHIVE}" | awk '{print $1}')
if [[ "${ACTUAL_SHA512}" != "${LATEST_SHA512}" ]]; then
  echo "Error: SHA512 mismatch! Expected ${LATEST_SHA512}, got ${ACTUAL_SHA512}" >&2
  exit 1
fi

# Test binary extraction and file attributes
tar -xz -C "${TMP_DIR}" -f "${ARCHIVE}" antigravity
chmod +x "${TMP_DIR}/antigravity"
if [[ ! -x "${TMP_DIR}/antigravity" ]]; then
  echo "Error: Extracted antigravity binary is not executable" >&2
  exit 1
fi

# Atomically update Dockerfile
TMP_DOCKERFILE="${TMP_DIR}/Dockerfile.tmp"
SAFE_URL="${LATEST_URL//&/\\&}"
sed -E \
  -e "s|^ARG AGY_VERSION=\".*\"|ARG AGY_VERSION=\"${LATEST_VERSION}\"|" \
  -e "s|^ARG AGY_URL=\".*\"|ARG AGY_URL=\"${SAFE_URL}\"|" \
  -e "s|^ARG AGY_SHA512=\".*\"|ARG AGY_SHA512=\"${LATEST_SHA512}\"|" \
  "${DOCKERFILE}" > "${TMP_DOCKERFILE}"

mv "${TMP_DOCKERFILE}" "${DOCKERFILE}"

echo "Successfully updated Dockerfile to agy ${LATEST_VERSION}."
