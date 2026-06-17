# BlackBoard/src/slack_gate.py
# @ai-rules:
# 1. [Constraint]: All K8s API calls MUST use asyncio.to_thread() -- kubernetes client is synchronous.
# 2. [Pattern]: Follows Observer start/stop lifecycle (same as kargo.py). Background _sync_loop task.
# 3. [Pattern]: Fail-closed -- empty groups = maintainer-only. No `if groups:` guard on instantiation.
# 4. [Gotcha]: K8s client initialized ONCE in start() via _init_k8s_client(), reused across syncs.
# 5. [Pattern]: OCP Groups store full emails (strategy c from probe). emailDomain is safety fallback only.
# 6. [Contract]: Every check() call emits INFO log: user, result, reason. Enables audit trail.
# 7. [Pattern]: _healthy=True after any successful sync. Stays True on mid-run failure (stale set kept).
#    _healthy=False only if startup never succeeded (empty set, maintainer-only).
"""OCP Group-based Slack access gate -- in-memory frozenset, periodic K8s API sync."""
from __future__ import annotations

import asyncio
import hashlib
import logging

logger = logging.getLogger("darwin.slack_gate")


def _mask_email(email: str) -> str:
    """Mask email for audit logs: first char + *** + @domain."""
    if not email or "@" not in email:
        return email or "<empty>"
    local, domain = email.rsplit("@", 1)
    return f"{local[0]}***@{domain}" if local else f"***@{domain}"

_K8S_TIMEOUT = (5, 10)  # (connect_timeout, read_timeout) for K8s API calls


class SlackAccessGate:
    """Gate Slack handler entry points based on OCP Group membership.

    Fetches group members from the cluster API, builds an in-memory frozenset
    of allowed emails, and checks incoming Slack users against it.
    Maintainer emails always bypass the gate.
    """

    def __init__(
        self,
        group_names: list[str],
        maintainer_emails: set[str],
        email_domain: str = "",
        sync_interval: int = 300,
    ):
        self._group_names = group_names
        self._maintainer_emails = {e.lower() for e in maintainer_emails}
        self._email_domain = email_domain.lower()
        self._sync_interval = sync_interval
        self._allowed_emails: frozenset[str] = frozenset()
        self._healthy: bool = False
        self._k8s_api = None
        self._task: asyncio.Task | None = None

    async def start(self):
        try:
            await asyncio.to_thread(self._init_k8s_client)
            await self._sync()
        except Exception as e:
            logger.critical("Slack access gate startup failed: %s. Maintainer-only mode.", e)
        self._task = asyncio.create_task(self._sync_loop())

    def _init_k8s_client(self):
        from kubernetes import client, config
        try:
            config.load_incluster_config()
        except config.ConfigException:
            config.load_kube_config()
        self._k8s_api = client.CustomObjectsApi()

    async def stop(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def check(self, email: str) -> bool:
        if not email:
            logger.info("slack_access_gate: user=<empty> result=deny reason=no_email")
            return False
        normalized = email.strip().lower()
        masked = _mask_email(normalized)
        if normalized in self._maintainer_emails:
            logger.info("slack_access_gate: user=%s result=allow reason=maintainer", masked)
            return True
        allowed = normalized in self._allowed_emails
        reason = "group_member" if allowed else ("unhealthy" if not self._healthy else "not_in_group")
        logger.info(
            "slack_access_gate: user=%s result=%s reason=%s",
            masked, "allow" if allowed else "deny", reason,
        )
        return allowed

    async def _sync(self):
        if not self._k8s_api:
            await asyncio.to_thread(self._init_k8s_client)
        emails = await asyncio.to_thread(self._fetch_group_members)
        self._allowed_emails = frozenset(emails)
        self._healthy = True
        if not emails and self._group_names:
            logger.warning(
                "Access sync: 0 emails resolved from %d configured groups -- "
                "all non-maintainer users will be denied. Check group names and RBAC.",
                len(self._group_names),
            )
        else:
            logger.info("Access sync: %d allowed emails from %d groups", len(emails), len(self._group_names))

    def _fetch_group_members(self) -> set[str]:
        from kubernetes.client.exceptions import ApiException
        if not self._k8s_api:
            raise RuntimeError("K8s client not initialized")
        emails: set[str] = set()
        unmapped = 0
        for name in self._group_names:
            try:
                group = self._k8s_api.get_cluster_custom_object(
                    "user.openshift.io", "v1", "groups", name,
                    _request_timeout=_K8S_TIMEOUT,
                )
            except ApiException as e:
                if e.status == 404:
                    logger.warning("OCP group '%s' not found (404), skipping", name)
                elif e.status in (401, 403):
                    logger.error("OCP group '%s' RBAC error (%d), skipping -- check ClusterRole", name, e.status)
                else:
                    logger.warning("OCP group '%s' fetch failed (%d), skipping", name, e.status)
                continue
            for username in group.get("users") or []:
                if "@" in username:
                    emails.add(username.lower())
                elif self._email_domain:
                    emails.add(f"{username}@{self._email_domain}".lower())
                else:
                    unmapped += 1
        if unmapped:
            logger.warning(
                "Access sync: %d usernames could not be mapped to email "
                "(no @ and SLACK_ACCESS_EMAIL_DOMAIN is empty)", unmapped,
            )
        return emails

    async def _sync_loop(self):
        while True:
            await asyncio.sleep(self._sync_interval)
            try:
                await self._sync()
            except Exception as e:
                logger.warning("Access sync failed, keeping stale set: %s", e)
