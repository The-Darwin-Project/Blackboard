# BlackBoard/src/agents/sysadmin.py
# SysAdmin Agent - executes approved plans via Gemini CLI sidecar
"""
Agent 3: The SysAdmin (The Executor)

Role: Safety & Execution
Nature: Hybrid (Python orchestrator calling Gemini CLI sidecar)

The SysAdmin reads approved plans and executes them via the Gemini CLI
sidecar container, which performs Git operations agentically.

AIR GAP ENFORCEMENT:
- This module may import httpx (for sidecar communication)
- This module may import redis (for Blackboard access)
- This module CANNOT import vertexai
"""
from __future__ import annotations

import functools
import json
import logging
import os
import re
from typing import TYPE_CHECKING, Optional

import httpx

# AIR GAP ENFORCEMENT: These imports are FORBIDDEN
# import vertexai  # FORBIDDEN
# from vertexai import *  # FORBIDDEN

if TYPE_CHECKING:
    from ..models import Plan
    from ..state.blackboard import BlackboardState

logger = logging.getLogger(__name__)

# GitHub App configuration
GITHUB_REPOSITORY = os.getenv("GITHUB_REPOSITORY", "The-Darwin-Project/gitops")

# =============================================================================
# Safety Decorator
# =============================================================================

FORBIDDEN_PATTERNS = [
    r"rm\s+-rf",
    r"rm\s+-r\s+/",
    r"delete\s+volume",
    r"drop\s+database",
    r"drop\s+table",
    r"truncate\s+table",
    r"kubectl\s+delete\s+namespace",
    r"kubectl\s+delete\s+pv",
    r"--force\s+--grace-period=0",
    r"git\s+push\s+--force",
    r"git\s+push\s+-f",
    r">\s*/dev/sd",
    r"mkfs\.",
    r"dd\s+if=",
]


class SecurityError(Exception):
    """Raised when a forbidden operation is detected."""
    pass


def safe_execution(func):
    """
    Safety decorator that blocks dangerous operations.
    
    Scans the plan context for forbidden patterns before execution.
    """
    @functools.wraps(func)
    def wrapper(self, plan_context: str, *args, **kwargs):
        # Scan for forbidden patterns
        for pattern in FORBIDDEN_PATTERNS:
            if re.search(pattern, plan_context, re.IGNORECASE):
                logger.error(f"SECURITY BLOCK: Forbidden pattern detected: {pattern}")
                raise SecurityError(f"Blocked forbidden pattern: {pattern}")
        
        return func(self, plan_context, *args, **kwargs)
    
    return wrapper


# =============================================================================
# SysAdmin Agent
# =============================================================================

class SysAdmin:
    """
    The SysAdmin agent - safe execution of infrastructure changes.
    
    Responsibilities:
    - Read approved plans from Blackboard
    - Validate plans against safety rules
    - Execute plans via Gemini CLI
    - Record execution results
    
    Uses validated Gemini CLI pattern:
    - --non-interactive (not --headless, which is deprecated)
    - --output-format json for structured output
    - GOOGLE_GENAI_USE_VERTEXAI=true for Vertex AI backend
    """
    
    def __init__(self, blackboard: "BlackboardState"):
        self.blackboard = blackboard
        
        # Configuration
        self.git_repo_path = os.getenv("GIT_REPO_PATH", "/tmp/darwin-gitops")
        self.dry_run = os.getenv("SYSADMIN_DRY_RUN", "false").lower() == "true"
        self.auto_approve = os.getenv("SYSADMIN_AUTO_APPROVE", "false").lower() == "true"
        
        # Gemini sidecar configuration (runs as localhost sidecar container)
        self.gemini_sidecar_url = os.getenv("GEMINI_SIDECAR_URL", "http://localhost:9090")
        
        # GitHub App auth (optional - for token refresh)
        self._github_auth: Optional["GitHubAppAuth"] = None
    
    def _get_github_auth(self) -> Optional["GitHubAppAuth"]:
        """
        Get GitHub App auth handler if configured.
        
        Lazy initialization to avoid import errors when GitHub App is not configured.
        """
        if self._github_auth is None:
            try:
                from ..utils.github_app import GitHubAppAuth
                self._github_auth = GitHubAppAuth()
                logger.info("GitHub App authentication initialized")
            except (ImportError, ValueError) as e:
                logger.warning(f"GitHub App auth not available: {e}")
                self._github_auth = None  # type: ignore
        return self._github_auth
    
    def _refresh_git_credentials(self) -> bool:
        """
        Refresh git credentials using GitHub App token.
        
        Called before git push to ensure token is valid.
        Returns True if credentials were refreshed, False otherwise.
        """
        auth = self._get_github_auth()
        if auth is None:
            logger.warning("GitHub App auth not configured, skipping credential refresh")
            return False
        
        try:
            auth.configure_git_credentials(self.git_repo_path, GITHUB_REPOSITORY)
            return True
        except Exception as e:
            logger.error(f"Failed to refresh git credentials: {e}")
            return False
    
    # Fallback service to Helm values path mapping (used when GitOps not in telemetry)
    SERVICE_HELM_PATHS = {
        "darwin-store": "Store/helm/values.yaml",
        "darwin-brain": "BlackBoard/helm/values.yaml",
        "darwin-blackboard": "BlackBoard/helm/values.yaml",
    }
    
    async def _get_gitops_info(self, service: str) -> tuple[str, str]:
        """
        Get GitOps repository and helm path for a service.
        
        First tries to look up from service registry (populated from telemetry).
        Falls back to hardcoded mapping if not found.
        
        Returns (repo, helm_path) tuple.
        """
        # Try to get from service registry first
        svc = await self.blackboard.get_service(service)
        if svc and svc.gitops_repo and svc.gitops_helm_path:
            logger.info(f"Using GitOps info from telemetry: {svc.gitops_repo}/{svc.gitops_helm_path}")
            return svc.gitops_repo, svc.gitops_helm_path
        
        # Fallback to hardcoded mapping
        logger.warning(f"No GitOps info in telemetry for {service}, using fallback mapping")
        helm_path = self._get_helm_path_fallback(service)
        
        # Infer repo from helm path
        repo_prefix = helm_path.split("/")[0]  # e.g., "Store" from "Store/helm/values.yaml"
        repo = f"The-Darwin-Project/{repo_prefix}"
        
        return repo, helm_path
    
    def _get_helm_path_fallback(self, service: str) -> str:
        """Fallback: Get the Helm values.yaml path for a service from hardcoded mapping."""
        # Try exact match first
        if service in self.SERVICE_HELM_PATHS:
            return self.SERVICE_HELM_PATHS[service]
        
        # Try partial match (e.g., "store" matches "darwin-store")
        for svc_name, path in self.SERVICE_HELM_PATHS.items():
            if service.lower() in svc_name.lower() or svc_name.lower() in service.lower():
                return path
        
        # Default: assume service name maps to directory
        return f"{service}/helm/values.yaml"
    
    def _build_prompt(self, plan: "Plan", gitops_repo: str, helm_path: str) -> str:
        """
        Build the prompt for Gemini CLI.
        
        Formats the plan into clear, explicit instructions for the AI agent
        to perform GitOps operations.
        
        Args:
            plan: The plan to execute
            gitops_repo: GitHub repository (e.g., "The-Darwin-Project/Store")
            helm_path: Path to Helm values within repo (e.g., "helm/values.yaml")
        """
        
        prompt_parts = [
            "You are a DevOps engineer performing GitOps operations.",
            "Execute the following infrastructure modification plan by editing files and committing to git.",
            "",
            f"=== PLAN DETAILS ===",
            f"Action: {plan.action.value}",
            f"Target Service: {plan.service}",
            f"Helm Values File: {helm_path}",
            f"Reason: {plan.reason}",
            "",
            "Parameters:",
            json.dumps(plan.params, indent=2),
            "",
            "=== EXECUTION STEPS ===",
        ]
        
        # Add action-specific instructions with explicit commands
        if plan.action.value == "scale":
            replicas = plan.params.get("replicas", 2)
            prompt_parts.extend([
                f"1. Open the file: {helm_path}",
                f"2. Find the 'replicaCount' field and change its value to {replicas}",
                f"3. Save the file",
                f"4. Run: git add {helm_path}",
                f"5. Run: git commit -m \"scale({plan.service}): Update replicaCount to {replicas}\"",
                f"6. Run: git push origin main",
            ])
        
        elif plan.action.value == "rollback":
            version = plan.params.get("version", "previous")
            prompt_parts.extend([
                f"1. Open the file: {helm_path}",
                f"2. Find the 'image.tag' field and change its value to \"{version}\"",
                f"3. Save the file",
                f"4. Run: git add {helm_path}",
                f"5. Run: git commit -m \"rollback({plan.service}): Revert to version {version}\"",
                f"6. Run: git push origin main",
            ])
        
        elif plan.action.value == "reconfig":
            config = plan.params.get("config", {})
            prompt_parts.extend([
                f"1. Open the file: {helm_path}",
                f"2. Apply these configuration changes: {json.dumps(config)}",
                f"3. Save the file",
                f"4. Run: git add {helm_path}",
                f"5. Run: git commit -m \"reconfig({plan.service}): Update configuration\"",
                f"6. Run: git push origin main",
            ])
        
        elif plan.action.value == "failover":
            target = plan.params.get("target", "standby")
            prompt_parts.extend([
                f"1. Open the file: {helm_path}",
                f"2. Update the service routing to point to '{target}'",
                f"3. Save the file",
                f"4. Run: git add {helm_path}",
                f"5. Run: git commit -m \"failover({plan.service}): Switch to {target}\"",
                f"6. Run: git push origin main",
            ])
        
        elif plan.action.value == "optimize":
            optimization = plan.params.get("optimization", "resources")
            prompt_parts.extend([
                f"1. Open the file: {helm_path}",
                f"2. Apply optimization: {optimization}",
                f"3. Save the file",
                f"4. Run: git add {helm_path}",
                f"5. Run: git commit -m \"optimize({plan.service}): Apply {optimization}\"",
                f"6. Run: git push origin main",
            ])
        
        prompt_parts.extend([
            "",
            "=== SAFETY RULES ===",
            "- Only modify the specified Helm values file",
            "- Do NOT delete any files or resources",
            "- Do NOT use --force with git commands",
            "- If git push fails due to conflicts, STOP and report the error",
            "",
            f"Working directory: {self.git_repo_path}",
            "",
            "Execute these steps now.",
        ])
        
        return "\n".join(prompt_parts)
    
    @safe_execution
    async def _execute_with_sidecar(self, plan_context: str, gitops_repo: str = None) -> dict:
        """
        Execute the plan via Gemini CLI sidecar.
        
        Calls the gemini sidecar HTTP endpoint which:
        1. Generates fresh GitHub App token (handles 1-hour TTL)
        2. Clones/updates the target repo dynamically
        3. Runs gemini CLI with the prompt
        
        Args:
            plan_context: The prompt for gemini CLI
            gitops_repo: Repository in owner/repo format (e.g., "The-Darwin-Project/Store")
        """
        logger.info(f"Executing via Gemini sidecar at {self.gemini_sidecar_url}...")
        
        if self.dry_run:
            logger.info("DRY RUN: Would call Gemini sidecar")
            return {
                "status": "dry_run",
                "message": "Dry run - no actual execution",
            }
        
        # Construct full repo URL from owner/repo format
        repo_url = f"https://github.com/{gitops_repo}.git" if gitops_repo else None
        if repo_url:
            logger.info(f"Target repo: {repo_url}")
        
        try:
            async with httpx.AsyncClient(timeout=310.0) as client:  # Slightly longer than sidecar timeout
                response = await client.post(
                    f"{self.gemini_sidecar_url}/execute",
                    json={
                        "prompt": plan_context,
                        "autoApprove": self.auto_approve,
                        "repoUrl": repo_url,  # Sidecar handles token generation and cloning
                        "cwd": self.git_repo_path,
                    },
                )
                
                result = response.json()
                
                if response.status_code != 200:
                    logger.error(f"Sidecar returned error: {result}")
                    return {
                        "status": "error",
                        "message": result.get("error", "Unknown sidecar error"),
                    }
                
                if result.get("status") == "success":
                    logger.info("Gemini sidecar execution completed successfully")
                else:
                    logger.warning(f"Sidecar returned status: {result.get('status')}")
                
                return result
        
        except httpx.TimeoutException:
            logger.error("Gemini sidecar execution timed out")
            return {
                "status": "timeout",
                "message": "Execution timed out after 5 minutes",
            }
        
        except httpx.ConnectError:
            logger.error(f"Cannot connect to Gemini sidecar at {self.gemini_sidecar_url}")
            return {
                "status": "error",
                "message": f"Gemini sidecar not available at {self.gemini_sidecar_url}. Is the sidecar container running?",
            }
        
        except Exception as e:
            logger.error(f"Sidecar execution error: {e}")
            return {
                "status": "error",
                "message": str(e),
            }
    
    async def execute_plan(self, plan: "Plan") -> str:
        """
        Execute an approved plan.
        
        This is the main entry point called by the plans route.
        
        Returns a result string describing the execution outcome.
        """
        logger.info(f"Executing plan: {plan.id} - {plan.action.value} {plan.service}")
        
        # Look up GitOps coordinates from service registry (populated from telemetry)
        gitops_repo, helm_path = await self._get_gitops_info(plan.service)
        logger.info(f"GitOps target: {gitops_repo}/{helm_path}")
        
        # Build the prompt with GitOps info
        prompt = self._build_prompt(plan, gitops_repo, helm_path)
        
        # Execute via sidecar (with safety check)
        # Pass gitops_repo so sidecar can clone the correct repository
        try:
            result = await self._execute_with_sidecar(prompt, gitops_repo)
            
            if result["status"] == "success":
                return f"Plan executed successfully. Output: {json.dumps(result.get('output', {}))}"
            elif result["status"] == "dry_run":
                return f"Dry run completed. Command: {result.get('command', [])}"
            else:
                return f"Execution failed: {result.get('message', result.get('stderr', 'Unknown error'))}"
        
        except SecurityError as e:
            logger.error(f"Security block during execution: {e}")
            raise
        
        except Exception as e:
            logger.error(f"Execution error: {e}")
            return f"Execution failed with error: {e}"
    
    def validate_plan(self, plan: "Plan") -> tuple[bool, str]:
        """
        Validate a plan before execution.
        
        Checks safety rules without actually executing.
        
        Returns (is_valid, message).
        """
        prompt = self._build_prompt(plan)
        
        # Check for forbidden patterns
        for pattern in FORBIDDEN_PATTERNS:
            if re.search(pattern, prompt, re.IGNORECASE):
                return False, f"Plan contains forbidden pattern: {pattern}"
        
        # Check that service exists in topology
        # (This would require async, so we skip for sync validation)
        
        return True, "Plan validated successfully"
    
    def can_auto_approve(self, plan: "Plan") -> tuple[bool, str]:
        """
        Determine if a plan can be auto-approved.
        
        Auto-approval policy (per Agent Definitions document):
        - Values-only changes (scaling, toggles, config values) → AUTO-APPROVE
        - Structural changes (templates, source code) → Require human approval
        
        Returns (can_approve, reason).
        """
        if not self.auto_approve:
            return False, "Auto-approval disabled (SYSADMIN_AUTO_APPROVE=false)"
        
        # Actions that are always values-only (safe for auto-approval)
        values_only_actions = {"scale", "reconfig"}
        
        # Actions that may require structural changes (need human review)
        structural_actions = {"failover", "optimize"}
        
        # Rollback is conditionally values-only
        # - If just changing image tag → values-only
        # - If rolling back templates → structural
        
        action = plan.action.value
        
        if action in values_only_actions:
            return True, f"Auto-approved: '{action}' is a values-only change"
        
        elif action == "rollback":
            # Check if it's just a version/tag change (safe) or structural
            params = plan.params or {}
            if params.get("template_rollback") or params.get("structural"):
                return False, "Rollback requires structural changes - human approval needed"
            return True, "Auto-approved: rollback is version-only change"
        
        elif action in structural_actions:
            # Check if explicitly marked as safe
            params = plan.params or {}
            if params.get("values_only"):
                return True, f"Auto-approved: '{action}' marked as values_only"
            return False, f"'{action}' may require structural changes - human approval needed"
        
        else:
            # Unknown action - require human approval
            return False, f"Unknown action '{action}' - human approval required"
