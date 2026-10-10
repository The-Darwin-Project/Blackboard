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

# Pin the exact bucket + path prefix and allow only plain path characters (no whitespace,
# newlines, quotes, '&', '|' or '\\'), so the URL can be written into the Dockerfile verbatim.
# Path traversal (..) is explicitly forbidden.
if [[ "${LATEST_URL}" =~ \.\. ]]; then
  echo "Error: Path traversal (..) in URL is forbidden: '${LATEST_URL}'" >&2
  exit 1
fi

AGY_URL_RE='^https://storage\.googleapis\.com/antigravity-public/antigravity-cli/[A-Za-z0-9._/-]+\.tar\.gz$'
if [[ ! "${LATEST_URL}" =~ ${AGY_URL_RE} ]]; then
  echo "Error: Invalid URL '${LATEST_URL}', must be https://storage.googleapis.com/antigravity-public/antigravity-cli/<path>.tar.gz" >&2
  exit 1
fi

if [[ ! "${LATEST_SHA512}" =~ ^[a-fA-F0-9]{128}$ ]]; then
  echo "Error: Invalid sha512 checksum format in manifest" >&2
  exit 1
fi

CURRENT_VERSION=$(grep -E '^ARG AGY_VERSION=' "${DOCKERFILE}" | cut -d'"' -f2 || true)
if [[ -z "${CURRENT_VERSION}" ]]; then
  echo "Error: could not read 'ARG AGY_VERSION=\"...\"' from ${DOCKERFILE} (was the ARG line reformatted?)" >&2
  exit 1
fi

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

# Rewrite the three ARG lines without sed: every value was validated above, but a bash
# line loop never interprets the replacement text (no delimiter/flag/newline injection).
# The temp file lives next to the Dockerfile so the final mv is an atomic same-filesystem rename.
TMP_DOCKERFILE=$(mktemp "${DOCKERFILE}.XXXXXX")
trap 'rm -rf "${TMP_DIR}" "${TMP_DOCKERFILE}"' EXIT
FOUND_ARGS=0
while IFS= read -r line || [[ -n "${line}" ]]; do
  case "${line}" in
    'ARG AGY_VERSION="'*) line="ARG AGY_VERSION=\"${LATEST_VERSION}\""; FOUND_ARGS=$((FOUND_ARGS + 1)) ;;
    'ARG AGY_URL="'*)     line="ARG AGY_URL=\"${LATEST_URL}\"";         FOUND_ARGS=$((FOUND_ARGS + 1)) ;;
    'ARG AGY_SHA512="'*)  line="ARG AGY_SHA512=\"${LATEST_SHA512}\"";   FOUND_ARGS=$((FOUND_ARGS + 1)) ;;
  esac
  printf '%s\n' "${line}"
done < "${DOCKERFILE}" > "${TMP_DOCKERFILE}"

if [[ "${FOUND_ARGS}" -ne 3 ]]; then
  echo "Error: expected to rewrite 3 AGY_* ARG lines in ${DOCKERFILE}, rewrote ${FOUND_ARGS}; Dockerfile left unchanged" >&2
  exit 1
fi

chmod --reference="${DOCKERFILE}" "${TMP_DOCKERFILE}"
mv "${TMP_DOCKERFILE}" "${DOCKERFILE}"

echo "Successfully updated Dockerfile to agy ${LATEST_VERSION}."
# The SHA512 and URL come from the same unauthenticated manifest, so the hash only guards
# against corruption, not a compromised publisher. A human must confirm it out of band.
echo "NOTE: verify AGY_SHA512 (${LATEST_SHA512}) against an independent source before merging."
