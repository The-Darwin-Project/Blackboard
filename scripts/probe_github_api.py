#!/usr/bin/env python3
"""
Probe: Validate GitHub App installation token can discover PRs.

Step 5 of the github-headhunter plan. Tests 3 API paths:
  a) GET /repos/{owner}/{repo}/pulls?state=open
  b) GET /repos/{owner}/{repo}/pulls/{number}/requested_reviewers
  c) GET /search/issues?q=is:pr+is:open+review-requested:{slug}[bot]

Pass/Partial/Fail criteria:
  Pass: (a) + (b) succeed → repo-scoped discovery is primary
  Partial: (a) works, (b) fails → filter differently, REPOS env required
  Fail: (a) returns 403 → App lacks pull_requests:read permission

Usage:
  export GITHUB_APP_ID=<id>
  export GITHUB_INSTALLATION_ID=<id>
  export GITHUB_PRIVATE_KEY_PATH=/path/to/pem
  python scripts/probe_github_api.py [owner/repo] [pr_number]

Defaults: The-Darwin-Project/Store, PR #90
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.github_app import GitHubAppAuth
import requests


def main():
    repo = sys.argv[1] if len(sys.argv) > 1 else "The-Darwin-Project/Store"
    pr_number = int(sys.argv[2]) if len(sys.argv) > 2 else 90
    owner, repo_name = repo.split("/", 1)

    print(f"=== GitHub API Probe ===")
    print(f"Repo: {repo}")
    print(f"PR: #{pr_number}")
    print()

    # --- Auth ---
    try:
        auth = GitHubAppAuth()
        token = auth.get_token()
        print(f"[OK] Installation token obtained (expires in ~1hr)")
    except Exception as e:
        print(f"[FAIL] Cannot get installation token: {e}")
        print(f"\nResult: FAIL — App credentials not configured")
        sys.exit(1)

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    # --- Resolve App slug (needed for search qualifier) ---
    print("\n--- Resolving App identity ---")
    jwt_token = auth._create_jwt()
    app_resp = requests.get(
        "https://api.github.com/app",
        headers={"Authorization": f"Bearer {jwt_token}", "Accept": "application/vnd.github+json"},
        timeout=15,
    )
    app_slug = None
    if app_resp.status_code == 200:
        app_data = app_resp.json()
        app_slug = app_data.get("slug", "unknown")
        app_name = app_data.get("name", "unknown")
        print(f"[OK] App: {app_name} (slug: {app_slug})")
    else:
        print(f"[WARN] GET /app returned {app_resp.status_code}: {app_resp.text[:200]}")

    # --- Test (a): List open PRs ---
    print(f"\n--- Test (a): GET /repos/{owner}/{repo_name}/pulls?state=open ---")
    resp_a = requests.get(
        f"https://api.github.com/repos/{owner}/{repo_name}/pulls",
        headers=headers,
        params={"state": "open", "per_page": "10"},
        timeout=15,
    )
    print(f"Status: {resp_a.status_code}")
    print(f"Rate-Limit-Remaining: {resp_a.headers.get('X-RateLimit-Remaining', '?')}")
    if resp_a.status_code == 200:
        prs = resp_a.json()
        print(f"[OK] Found {len(prs)} open PR(s)")
        for pr in prs[:3]:
            print(f"  - #{pr['number']}: {pr['title']} (state={pr['state']})")
        test_a = "PASS"
    elif resp_a.status_code == 403:
        print(f"[FAIL] 403 Forbidden — App lacks pull_requests:read")
        print(f"  Body: {resp_a.text[:300]}")
        test_a = "FAIL"
    else:
        print(f"[WARN] Unexpected: {resp_a.text[:200]}")
        test_a = "WARN"

    # --- Test (b): Read requested reviewers ---
    print(f"\n--- Test (b): GET /repos/{owner}/{repo_name}/pulls/{pr_number}/requested_reviewers ---")
    resp_b = requests.get(
        f"https://api.github.com/repos/{owner}/{repo_name}/pulls/{pr_number}/requested_reviewers",
        headers=headers,
        timeout=15,
    )
    print(f"Status: {resp_b.status_code}")
    if resp_b.status_code == 200:
        reviewers = resp_b.json()
        users = [u["login"] for u in reviewers.get("users", [])]
        teams = [t["slug"] for t in reviewers.get("teams", [])]
        print(f"[OK] Reviewers: users={users}, teams={teams}")
        test_b = "PASS"
    elif resp_b.status_code == 404:
        print(f"[WARN] PR #{pr_number} not found or no reviewer data")
        test_b = "PARTIAL"
    elif resp_b.status_code == 403:
        print(f"[FAIL] 403 — cannot read reviewers")
        test_b = "FAIL"
    else:
        print(f"[WARN] Unexpected: {resp_b.text[:200]}")
        test_b = "WARN"

    # --- Test (c): Search API ---
    print(f"\n--- Test (c): Search issues (cross-repo discovery) ---")
    if app_slug:
        query = f"is:pr is:open review-requested:{app_slug}[bot]"
        print(f"Query: {query}")
        resp_c = requests.get(
            "https://api.github.com/search/issues",
            headers=headers,
            params={"q": query, "per_page": "5"},
            timeout=15,
        )
        print(f"Status: {resp_c.status_code}")
        print(f"Rate-Limit-Remaining: {resp_c.headers.get('X-RateLimit-Remaining', '?')}")
        if resp_c.status_code == 200:
            results = resp_c.json()
            print(f"[OK] Search returned {results.get('total_count', 0)} results")
            for item in results.get("items", [])[:3]:
                print(f"  - {item.get('repository_url', '').split('/')[-1]} #{item['number']}: {item['title']}")
            test_c = "PASS"
        elif resp_c.status_code == 422:
            print(f"[WARN] 422 — qualifier not recognized or invalid")
            print(f"  Body: {resp_c.text[:300]}")
            test_c = "FAIL"
        elif resp_c.status_code == 403:
            print(f"[WARN] 403 — Search not available for this token type")
            test_c = "FAIL"
        else:
            print(f"[WARN] Unexpected: {resp_c.text[:200]}")
            test_c = "WARN"
    else:
        print("[SKIP] Cannot test search — App slug not resolved")
        test_c = "SKIP"

    # --- Summary ---
    print(f"\n{'='*50}")
    print(f"PROBE RESULTS")
    print(f"{'='*50}")
    print(f"  (a) List PRs:             {test_a}")
    print(f"  (b) Read reviewers:       {test_b}")
    print(f"  (c) Search (cross-repo):  {test_c}")
    print()

    if test_a == "PASS" and test_b in ("PASS", "PARTIAL"):
        print("VERDICT: PASS")
        print("  → Repo-scoped PR listing + reviewer read works.")
        print("  → Discovery: iterate HEADHUNTER_GITHUB_REPOS, list PRs, filter by requested_reviewers.")
        if test_c == "PASS":
            print("  → BONUS: Cross-repo search also works (can discover PRs across all App repos).")
        else:
            print("  → Search not available — HEADHUNTER_GITHUB_REPOS env var is REQUIRED.")
        sys.exit(0)
    elif test_a == "PASS":
        print("VERDICT: PARTIAL")
        print("  → Can list PRs but cannot read requested_reviewers.")
        print("  → Filter by other signals (assignee, mentions in comments).")
        print("  → HEADHUNTER_GITHUB_REPOS env var is REQUIRED.")
        sys.exit(0)
    else:
        print("VERDICT: FAIL")
        print("  → App lacks pull_requests:read permission.")
        print("  → Update GitHub App permissions before proceeding with GitHubPlatform adapter.")
        sys.exit(1)


if __name__ == "__main__":
    main()
