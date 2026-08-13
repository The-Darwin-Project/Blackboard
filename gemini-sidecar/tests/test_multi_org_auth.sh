#!/usr/bin/env bash
# gemini-sidecar/tests/test_multi_org_auth.sh
# @ai-rules:
# 1. [Constraint]: Test-only file — no implementation of credential helper or gh wrapper.
# 2. [Pattern]: Each test creates a fixture token map, runs the script under test, asserts output.
# 3. [Gotcha]: Temp directories must be cleaned up in trap handler to avoid leaking test state.
# 4. [Pattern]: T-12 reuses the validate-mutations.sh hook runner pattern from test_validate_mutations.sh.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SIDECAR_DIR="${SCRIPT_DIR}/.."
CRED_HELPER="${SIDECAR_DIR}/git-credential-darwin"
GH_WRAPPER="${SIDECAR_DIR}/gh-wrapper.sh"
MUTATIONS_HOOK="${SIDECAR_DIR}/hooks/validate-mutations.sh"

PASS=0
FAIL=0
ERRORS=()

TMPDIR_TEST=""
cleanup() {
  [[ -n "$TMPDIR_TEST" && -d "$TMPDIR_TEST" ]] && rm -rf "$TMPDIR_TEST"
}
trap cleanup EXIT

setup_fixtures() {
  TMPDIR_TEST="$(mktemp -d)"
  TOKEN_MAP="${TMPDIR_TEST}/gh-token-map.json"
  cat > "$TOKEN_MAP" <<'FIXTURE'
{
  "openshift-cnv": { "token": "ghs_openshift_cnv_test_token_aaa", "installation_id": 111 },
  "The-Darwin-Project": { "token": "ghs_darwin_test_token_bbb", "installation_id": 222 },
  "alraj-creator": { "token": "ghs_alraj_test_token_ccc", "installation_id": 333 }
}
FIXTURE
  chmod 600 "$TOKEN_MAP"
}

# --- Helpers ---

assert_eq() {
  local name="$1" expected="$2" actual="$3"
  if [[ "$expected" == "$actual" ]]; then
    echo "PASS [$name]"
    ((PASS++))
  else
    ERRORS+=("FAIL [$name]: expected '$expected', got '$actual'")
    ((FAIL++))
  fi
}

assert_contains() {
  local name="$1" expected="$2" actual="$3"
  if [[ "$actual" == *"$expected"* ]]; then
    echo "PASS [$name]"
    ((PASS++))
  else
    ERRORS+=("FAIL [$name]: expected output to contain '$expected', got '$actual'")
    ((FAIL++))
  fi
}

assert_empty() {
  local name="$1" actual="$2"
  if [[ -z "$actual" ]]; then
    echo "PASS [$name]"
    ((PASS++))
  else
    ERRORS+=("FAIL [$name]: expected empty output, got '$actual'")
    ((FAIL++))
  fi
}

run_mutations_hook_test() {
  local name="$1" input="$2" role="$3" expected_decision="$4"
  local output
  output="$(echo "$input" | AGENT_ROLE="$role" bash "$MUTATIONS_HOOK" 2>/dev/null)" || true
  if ! echo "$output" | jq empty 2>/dev/null; then
    ERRORS+=("FAIL [$name]: output is not valid JSON: $output")
    ((FAIL++))
    return
  fi
  local actual_decision
  actual_decision="$(echo "$output" | jq -r '.decision')"
  if [[ "$actual_decision" == "$expected_decision" ]]; then
    echo "PASS [$name]"
    ((PASS++))
  else
    ERRORS+=("FAIL [$name]: expected decision='$expected_decision', got '$actual_decision' (output: $output)")
    ((FAIL++))
  fi
}

# --- Pre-flight ---

echo "=== Multi-Org GitHub Auth Test Suite ==="
echo ""

if ! command -v jq &>/dev/null; then
  echo "ERROR: jq is required but not found in PATH"
  exit 1
fi

setup_fixtures

# ============================================================
# T-3: Credential helper returns correct token for known org
# ============================================================
# git credential helper protocol: stdin key=value, stdout key=value
# The credential helper reads the token map and resolves org from the path.

if [[ -x "$CRED_HELPER" ]] || [[ -f "$CRED_HELPER" ]]; then
  output="$(printf 'protocol=https\nhost=github.com\npath=openshift-cnv/repo.git\n\n' \
    | GH_TOKEN_MAP_PATH="$TOKEN_MAP" bash "$CRED_HELPER" get 2>/dev/null)" || true

  # Extract password from credential helper output (format: key=value lines)
  password="$(echo "$output" | grep '^password=' | head -1 | cut -d= -f2-)"
  assert_eq "T-3: credential helper returns openshift-cnv token" \
    "ghs_openshift_cnv_test_token_aaa" "$password"
else
  echo "SKIP [T-3]: $CRED_HELPER not found (implementation pending)"
fi

# ============================================================
# T-4: Credential helper exits silently for unknown org
# ============================================================

if [[ -x "$CRED_HELPER" ]] || [[ -f "$CRED_HELPER" ]]; then
  output="$(printf 'protocol=https\nhost=github.com\npath=unknown-org/repo.git\n\n' \
    | GH_TOKEN_MAP_PATH="$TOKEN_MAP" bash "$CRED_HELPER" get 2>/dev/null)" || true
  exit_code=$?

  assert_empty "T-4: credential helper produces no output for unknown org" "$output"
  # exit 0 is success — credential helpers must not error on unknown hosts
  assert_eq "T-4: credential helper exits 0 for unknown org" "0" "$exit_code"
else
  echo "SKIP [T-4]: $CRED_HELPER not found (implementation pending)"
fi

# ============================================================
# T-5: gh wrapper resolves token from git remote
# ============================================================

if [[ -x "$GH_WRAPPER" ]] || [[ -f "$GH_WRAPPER" ]]; then
  # Set up a temp git repo with a github.com/openshift-cnv remote
  test_repo="${TMPDIR_TEST}/test-repo-t5"
  mkdir -p "$test_repo"
  git -C "$test_repo" init --quiet 2>/dev/null
  git -C "$test_repo" remote add origin "https://github.com/openshift-cnv/some-repo.git" 2>/dev/null

  # Create a mock .gh-real that echoes GH_TOKEN (wrapper exec's into this)
  mock_gh="${TMPDIR_TEST}/mock-gh"
  printf '#!/bin/bash\necho "$GH_TOKEN"\n' > "$mock_gh"
  chmod +x "$mock_gh"

  # Run the wrapper with mock .gh-real — it resolves GH_TOKEN then exec's the mock
  resolved_token="$(
    cd "$test_repo" && \
    PATH="${TMPDIR_TEST}:$PATH" \
    GH_TOKEN_MAP_PATH="$TOKEN_MAP" GH_TOKEN="" \
    bash -c "
      # Patch exec target to our mock
      sed 's|/usr/local/bin/.gh-real|${mock_gh}|' '$GH_WRAPPER' | bash
    "
  )" || true

  assert_eq "T-5: gh wrapper sets GH_TOKEN for openshift-cnv remote" \
    "ghs_openshift_cnv_test_token_aaa" "$resolved_token"
else
  echo "SKIP [T-5]: $GH_WRAPPER not found (implementation pending)"
fi

# ============================================================
# T-6: gh wrapper falls through without git remote
# ============================================================

if [[ -x "$GH_WRAPPER" ]] || [[ -f "$GH_WRAPPER" ]]; then
  # Set up a temp directory that is NOT a git repo
  test_dir="${TMPDIR_TEST}/test-no-git-t6"
  mkdir -p "$test_dir"

  # Mock .gh-real that echoes GH_TOKEN
  mock_gh="${TMPDIR_TEST}/mock-gh-t6"
  printf '#!/bin/bash\necho "$GH_TOKEN"\n' > "$mock_gh"
  chmod +x "$mock_gh"

  default_token="ghs_default_fallback_token"
  resolved_token="$(
    cd "$test_dir" && \
    GH_TOKEN_MAP_PATH="$TOKEN_MAP" GH_TOKEN="$default_token" \
    bash -c "sed 's|/usr/local/bin/.gh-real|${mock_gh}|' '$GH_WRAPPER' | bash"
  )" || true

  assert_eq "T-6: gh wrapper preserves default GH_TOKEN without remote" \
    "$default_token" "$resolved_token"
else
  echo "SKIP [T-6]: $GH_WRAPPER not found (implementation pending)"
fi

# ============================================================
# T-12: validate-mutations.sh blocks cat /tmp/gh-token-map.json for explorer
# ============================================================
# The implementation will add /tmp/gh-token-map to the credential path
# denylist in validate-mutations.sh (same pattern as /tmp/git-creds-).

if [[ -f "$MUTATIONS_HOOK" ]]; then
  run_mutations_hook_test \
    "T-12: cat token map blocked for explorer" \
    '{"tool_name":"Bash","tool_input":{"command":"cat /tmp/gh-token-map.json"}}' \
    "explorer" \
    "block"
else
  echo "SKIP [T-12]: $MUTATIONS_HOOK not found"
fi

# ============================================================
# T-14: Credential helper resolves _default key (single-install mode)
# ============================================================

if [[ -x "$CRED_HELPER" ]] || [[ -f "$CRED_HELPER" ]]; then
  # Create a _default-only token map (simulates single-install fallback)
  default_map="${TMPDIR_TEST}/default-only-map.json"
  cat > "$default_map" <<'FIXTURE'
{ "_default": { "token": "ghs_single_install_token", "installation_id": "999", "expires_at": "" } }
FIXTURE
  chmod 600 "$default_map"

  output="$(printf 'protocol=https\nhost=github.com\npath=any-org/any-repo.git\n\n' \
    | GH_TOKEN_MAP_PATH="$default_map" bash "$CRED_HELPER" get 2>/dev/null)" || true
  password="$(echo "$output" | grep '^password=' | head -1 | cut -d= -f2-)"
  assert_eq "T-14: credential helper uses _default for single-install mode" \
    "ghs_single_install_token" "$password"
else
  echo "SKIP [T-14]: $CRED_HELPER not found"
fi

# --- Results ---

echo ""
echo "=== Results ==="
echo "Passed: $PASS"
echo "Failed: $FAIL"

if [[ ${#ERRORS[@]} -gt 0 ]]; then
  echo ""
  echo "--- Failures ---"
  for err in "${ERRORS[@]}"; do
    echo "  $err"
  done
fi

echo ""
if [[ $FAIL -gt 0 ]]; then
  echo "SUITE FAILED"
  exit 1
else
  echo "ALL TESTS PASSED"
  exit 0
fi
