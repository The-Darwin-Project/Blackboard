# BlackBoard/tests/test_pii_redaction.py
# @ai-rules:
# 1. [Constraint]: Tests the shared src.utils.pii_redaction module used by both
#    LiveAPIAdapter (JARVIS MemoryCorpus) and Archivist (Vertex Ranking API).
"""
Tests for shared PII/secret redaction (src/utils/pii_redaction.py).

Codereview finding: the original single-site email-only redaction left several
outbound paths and a whole external-API call site unguarded, and didn't cover
non-email secret classes (API keys, tokens, IPs) at all.
"""
from __future__ import annotations

from src.utils.pii_redaction import redact_pii


class TestRedactEmails:
    def test_email_redacted(self):
        assert redact_pii("contact alice@example.com") == "contact [redacted-email]"

    def test_multiple_emails_redacted(self):
        result = redact_pii("alice@example.com and bob@example.co.uk")
        assert "alice@example.com" not in result
        assert "bob@example.co.uk" not in result
        assert result.count("[redacted-email]") == 2

    def test_no_email_unchanged(self):
        text = "no emails here, just plain text"
        assert redact_pii(text) == text


class TestRedactIpv4:
    def test_ipv4_redacted(self):
        assert redact_pii("server at 10.0.0.5 failed") == "server at [redacted-ip] failed"

    def test_multiple_ips_redacted(self):
        result = redact_pii("10.0.0.5 and 192.168.1.1")
        assert "10.0.0.5" not in result
        assert "192.168.1.1" not in result


class TestRedactSecrets:
    def test_bearer_token_redacted(self):
        result = redact_pii("Authorization: Bearer abc123.def456-ghi")
        assert "abc123.def456-ghi" not in result
        assert "Bearer [redacted-token]" in result

    def test_aws_key_redacted(self):
        result = redact_pii("access key: AKIAIOSFODNN7EXAMPLE")
        assert "AKIAIOSFODNN7EXAMPLE" not in result
        assert "[redacted-aws-key]" in result

    def test_google_api_key_redacted(self):
        key = "AIza" + "x" * 35
        result = redact_pii(f"the key is {key} for this project")
        assert key not in result
        assert "[redacted-google-api-key]" in result

    def test_github_token_redacted(self):
        token = "ghp_" + "a" * 36
        result = redact_pii(f"token={token}")
        assert token not in result
        assert "[redacted-github-token]" in result

    def test_slack_token_redacted(self):
        token = "xoxb-" + "1234567890"
        result = redact_pii(f"slack token {token}")
        assert token not in result
        assert "[redacted-slack-token]" in result

    def test_jwt_redacted(self):
        jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PYE"
        result = redact_pii(f"auth header: {jwt}")
        assert jwt not in result
        assert "[redacted-jwt]" in result

    def test_generic_keyed_secret_redacted(self):
        result = redact_pii('config: api_key="sk_live_abcdefghijklmnop"')
        assert "sk_live_abcdefghijklmnop" not in result
        assert "[redacted-secret]" in result

    def test_password_field_redacted(self):
        result = redact_pii("password: SuperSecret123456")
        assert "SuperSecret123456" not in result
        assert "[redacted-secret]" in result


class TestKeyedSecretScreamingSnakeCase:
    """Codereview HIGH finding: SCREAMING_SNAKE_CASE-prefixed names (the most common
    real-world secret-naming convention) previously bypassed the keyed-secret catch-all
    because '_' and the keyword's first letter are both \\w chars, so \\b never fired."""

    def test_db_password_redacted(self):
        result = redact_pii("DB_PASSWORD=supersecret123")
        assert "supersecret123" not in result
        assert "DB_PASSWORD=[redacted-secret]" in result

    def test_aws_secret_access_key_redacted(self):
        result = redact_pii("AWS_SECRET_ACCESS_KEY=abcdefgh12345678")
        assert "abcdefgh12345678" not in result
        assert "[redacted-secret]" in result

    def test_jwt_secret_env_var_redacted(self):
        result = redact_pii("JWT_SECRET=abcdefgh12345678")
        assert "abcdefgh12345678" not in result
        assert "[redacted-secret]" in result

    def test_compound_word_not_falsely_matched(self):
        """A compound word like MYPASSWORD (letter immediately before the keyword, no
        separator) should NOT match -- avoids over-matching unrelated identifiers."""
        text = "MYPASSWORD=abcdefgh12345678"
        assert redact_pii(text) == text


class TestKeyedSecretCharsetAndSeparator:
    """Codereview MEDIUM findings: value charset excluded common password punctuation,
    and the separator was always rewritten to '=' even when the original used ':'."""

    def test_punctuation_in_value_redacted(self):
        result = redact_pii("password: my!pass123456")
        assert "my!pass123456" not in result
        assert "[redacted-secret]" in result

    def test_colon_separator_preserved_not_rewritten_to_equals(self):
        result = redact_pii("token: abcdefgh12345678")
        assert "token:[redacted-secret]" in result
        assert "token=[redacted-secret]" not in result


class TestRedactCombined:
    def test_mixed_pii_all_redacted_in_one_pass(self):
        text = "Contact alice@example.com at 10.0.0.5 with Bearer sometoken123"
        result = redact_pii(text)
        assert "alice@example.com" not in result
        assert "10.0.0.5" not in result
        assert "sometoken123" not in result

    def test_empty_and_none_safe(self):
        assert redact_pii("") == ""
        assert redact_pii(None) is None

    def test_sentinel_strings_not_corrupted(self):
        """Regression guard: redaction must never alter control-flow sentinel strings
        that don't contain '@' (e.g. LiveAPIAdapter's "No handoff notes found.")."""
        sentinel = "No handoff notes found."
        assert redact_pii(sentinel) == sentinel


class TestKeyedSecretWhitespaceSeparator:
    """Whitespace before/after ':' or '=' must not bypass the keyed-secret pattern."""

    def test_spaces_around_equals(self):
        result = redact_pii("password = secretvalue123")
        assert "secretvalue123" not in result
        assert "password=[redacted-secret]" in result

    def test_spaces_around_colon(self):
        result = redact_pii("api_key : secretvalue123")
        assert "secretvalue123" not in result
        assert "api_key:[redacted-secret]" in result

    def test_space_only_before_separator(self):
        assert "secretvalue123" not in redact_pii("token =secretvalue123")

    def test_tab_before_separator(self):
        assert "secretvalue123" not in redact_pii("secret\t= secretvalue123")

    def test_quoted_value_with_spaces_around_equals(self):
        assert "sk_live_abcdefghijklmnop" not in redact_pii('api_key = "sk_live_abcdefghijklmnop"')

    def test_no_separator_unchanged(self):
        text = "the password is rotated weekly"
        assert redact_pii(text) == text


class TestRedactUrlCredentials:
    def test_basic_auth_password_redacted_host_preserved(self):
        result = redact_pii("clone https://deploy:hunter2pass@git.example.com/org/repo.git")
        assert "hunter2pass" not in result
        assert "deploy" not in result
        assert result == "clone https://[REDACTED]@git.example.com/org/repo.git"

    def test_scheme_variants(self):
        for scheme in ("postgres", "redis", "amqp"):
            result = redact_pii(f"{scheme}://user:p4ssw0rd@db.internal:5432/x")
            assert "p4ssw0rd" not in result
            assert f"{scheme}://[REDACTED]@db.internal:5432/x" in result

    def test_password_containing_at_sign_fully_redacted(self):
        result = redact_pii("https://user:p@ss@host.example.com/path")
        assert "p@ss" not in result and "ss@host" not in result
        assert "https://[REDACTED]@host.example.com/path" in result

    def test_url_without_credentials_unchanged(self):
        text = "see https://example.com:8443/path?x=1 for details"
        assert redact_pii(text) == text

    def test_port_is_not_mistaken_for_credentials(self):
        text = "connect to http://host:8080/a and mail later"
        assert redact_pii(text) == text


class TestRedactPemPrivateKeys:
    BODY = "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC7\nabcdEFGHijklMNOPqrstUVWX0123456789+/=="

    def test_full_block_redacted(self):
        text = f"key:\n-----BEGIN PRIVATE KEY-----\n{self.BODY}\n-----END PRIVATE KEY-----\nafter"
        result = redact_pii(text)
        assert "MIIEvQIBADANBg" not in result and "abcdEFGH" not in result
        assert result == "key:\n[REDACTED_PRIVATE_KEY]\nafter"

    def test_typed_headers(self):
        for kind in ("RSA PRIVATE KEY", "EC PRIVATE KEY", "OPENSSH PRIVATE KEY", "ENCRYPTED PRIVATE KEY"):
            text = f"-----BEGIN {kind}-----\n{self.BODY}\n-----END {kind}-----"
            assert redact_pii(text) == "[REDACTED_PRIVATE_KEY]"

    def test_unclosed_block_redacted_to_end_of_string(self):
        text = f"leading note\n-----BEGIN RSA PRIVATE KEY-----\n{self.BODY}"
        result = redact_pii(text)
        assert "MIIEvQIBADANBg" not in result and "abcdEFGH" not in result
        assert result == "leading note\n[REDACTED_PRIVATE_KEY]"

    def test_header_only_redacted(self):
        result = redact_pii("-----BEGIN PRIVATE KEY-----")
        assert "BEGIN" not in result
        assert "[REDACTED_PRIVATE_KEY]" in result

    def test_public_key_block_not_redacted(self):
        text = "-----BEGIN PUBLIC KEY-----\nMFkwEwYHKoZIzj0C\n-----END PUBLIC KEY-----"
        assert redact_pii(text) == text

    def test_multiple_blocks(self):
        block = f"-----BEGIN PRIVATE KEY-----\n{self.BODY}\n-----END PRIVATE KEY-----"
        result = redact_pii(f"{block}\nmid\n{block}")
        assert result == "[REDACTED_PRIVATE_KEY]\nmid\n[REDACTED_PRIVATE_KEY]"
