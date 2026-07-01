---
name: darwin-security-audit
description: Security vulnerability scanning and audit workflow. Detects ecosystem, runs scans, produces structured findings report.
roles: [security_analyst]
modes: [investigate]
---

# Security Audit Workflow

## Phase 1: Ecosystem Detection

Identify the target repository's technology stack by checking for:

- `package.json` / `package-lock.json` / `yarn.lock` → Node.js/TypeScript
- `requirements.txt` / `Pipfile` / `pyproject.toml` → Python
- `go.mod` / `go.sum` → Go
- `Containerfile` / `Dockerfile` → Container image
- `pom.xml` / `build.gradle` → Java/Kotlin

A single repository may have multiple ecosystems. Scan ALL of them.

## Phase 2: Vulnerability Scanning

For each detected ecosystem, run the appropriate scanning tools. These are pre-installed in your environment:

- `trivy` -- filesystem and image vulnerability scanning
- `grype` -- vulnerability matching against SBOM
- `syft` -- SBOM generation (CycloneDX, SPDX)
- `cosign` -- container image signature verification
- `skopeo` -- container image inspection (no daemon required)
- `oras` -- OCI artifact push/pull/discover
- `pip-audit` -- Python dependency vulnerability audit
- `npm audit` -- Node.js dependency audit (bundled with npm)

Capture scan output in JSON format when possible for structured parsing.

### Scan Targets

1. **Dependency vulnerabilities**: package manifests and lockfiles
2. **Container image vulnerabilities**: base image + installed packages
3. **SBOM generation**: produce a Software Bill of Materials for supply chain audits
4. **Signature verification**: check container image signatures when signing tools are available

## Phase 3: Findings Report

Structure your report as a findings table:

```
| CVE ID | Package | Current Version | Fixed Version | Severity | Auto-fixable |
|--------|---------|-----------------|---------------|----------|--------------|
| CVE-XXXX-YYYY | pkg-name | 1.2.3 | 1.2.4 | Critical | Yes (patch) |
| CVE-XXXX-ZZZZ | other-pkg | 2.0.0 | 3.0.0 | High | No (major) |
```

### Severity Classification

- **Critical/High**: Must be addressed. Auto-fixable if minor/patch bump resolves it.
- **Medium**: Flag for awareness. Skip unless explicitly requested.
- **Low**: Skip unless explicitly requested.

## Phase 4: Remediation Assessment

For each finding, classify the remediation path:

| Classification | Criteria | Action |
|---|---|---|
| **Auto-fixable** | Minor/patch version bump resolves the CVE | Recommend Developer auto-fix |
| **Breaking change** | Major version bump required | Flag for human review |
| **No fix available** | No patched version exists upstream | Flag for human with workaround if known |
| **Transitive** | Vulnerability is in a transitive dependency | Identify direct dependency to bump |

## Phase 5: Handoff

- Use `team_send_results` to deliver the full findings report
- If auto-fixable CVEs exist: recommend Developer dispatch with specific package bumps
- If only human-review items: report findings and recommend user triage
- If clean scan (zero vulnerabilities): report clean status

## Rules

- NEVER modify source code or push changes
- NEVER skip ecosystem detection -- scan everything present
- Include the raw scan command output as evidence alongside the summary table
- If a scan tool fails or is unavailable, report the gap and continue with available tools
- Time-box scanning to 10 minutes per ecosystem. Report partial results if exceeded.
