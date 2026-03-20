<!-- @ai-rules:
1. [Constraint]: Vulnerabilities reported via GitHub Security Advisories ONLY. Never suggest public issues.
2. [Pattern]: Security controls list references src/agents/security.py FORBIDDEN_PATTERNS. Keep in sync.
3. [Constraint]: Update "Supported Versions" table when major versions are released.
-->
# Security Policy

## Supported Versions

| Version | Supported |
| :--- | :--- |
| 1.x | Yes |

## Reporting a Vulnerability

**Do NOT open a public issue for security vulnerabilities.**

Please report security vulnerabilities through [GitHub Security Advisories](https://github.com/The-Darwin-Project/Blackboard/security/advisories/new).

### What to include

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

### Response Timeline

- **Acknowledgment:** Within 48 hours
- **Initial assessment:** Within 1 week
- **Fix or mitigation:** Depends on severity, targeting 30 days for critical issues

### Disclosure

We follow coordinated disclosure. We will work with you to understand the issue and agree on a disclosure timeline before any public announcement.

## Security Considerations

Darwin agents execute commands on Kubernetes clusters. The following security controls are in place:

- **FORBIDDEN_PATTERNS** in `src/agents/security.py` block destructive commands
- **Air Gap enforcement** via agent skill files limits each agent's capabilities
- **Structural changes** require user approval (Brain pauses for confirmation)
- **AI-generated content** is tagged in both Dashboard and Slack interfaces
- **Secrets** are injected via Kubernetes Secrets, never stored in the repository
