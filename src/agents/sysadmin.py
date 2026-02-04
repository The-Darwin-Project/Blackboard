# BlackBoard/src/agents/sysadmin.py
"""
Agent 3: The SysAdmin (The Executor)

Role: Safety & Execution
Nature: Hybrid (Python Wrapper around @google/gemini-cli)

The SysAdmin reads approved plans and executes them via the Gemini CLI
in headless mode, which performs Git operations agentically.

AIR GAP ENFORCEMENT:
- This module may import subprocess (for CLI execution)
- This module may import redis (for Blackboard access)
- This module CANNOT import vertexai
"""
from __future__ import annotations

import functools
import json
import logging
import os
import re
import subprocess
from typing import TYPE_CHECKING

# AIR GAP ENFORCEMENT: These imports are FORBIDDEN
# import vertexai  # FORBIDDEN
# from vertexai import *  # FORBIDDEN

if TYPE_CHECKING:
    from ..models import Plan
    from ..state.blackboard import BlackboardState

logger = logging.getLogger(__name__)

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
    
    def _build_prompt(self, plan: "Plan") -> str:
        """
        Build the prompt for Gemini CLI.
        
        Formats the plan into a clear instruction for the AI agent.
        """
        prompt_parts = [
            "You are a DevOps engineer. Execute the following infrastructure modification plan.",
            "",
            f"Action: {plan.action.value}",
            f"Target Service: {plan.service}",
            f"Reason: {plan.reason}",
            "",
            "Parameters:",
            json.dumps(plan.params, indent=2),
            "",
            "Instructions:",
        ]
        
        # Add action-specific instructions
        if plan.action.value == "scale":
            replicas = plan.params.get("replicas", 2)
            prompt_parts.append(
                f"1. Find the Kubernetes deployment or Helm values for '{plan.service}'"
            )
            prompt_parts.append(f"2. Update the replicas count to {replicas}")
            prompt_parts.append("3. Commit the change with a descriptive message")
        
        elif plan.action.value == "rollback":
            version = plan.params.get("version", "previous")
            prompt_parts.append(f"1. Find the deployment configuration for '{plan.service}'")
            prompt_parts.append(f"2. Update the image tag or version to '{version}'")
            prompt_parts.append("3. Commit the change with a descriptive message")
        
        elif plan.action.value == "reconfig":
            config = plan.params.get("config", {})
            prompt_parts.append(f"1. Find the ConfigMap or values file for '{plan.service}'")
            prompt_parts.append(f"2. Apply these configuration changes: {json.dumps(config)}")
            prompt_parts.append("3. Commit the change with a descriptive message")
        
        elif plan.action.value == "failover":
            target = plan.params.get("target", "standby")
            prompt_parts.append(f"1. Update the service routing to point to '{target}'")
            prompt_parts.append("2. Verify the target is healthy")
            prompt_parts.append("3. Commit the change with a descriptive message")
        
        elif plan.action.value == "optimize":
            optimization = plan.params.get("optimization", "resources")
            prompt_parts.append(f"1. Review current configuration for '{plan.service}'")
            prompt_parts.append(f"2. Apply optimization: {optimization}")
            prompt_parts.append("3. Commit the change with a descriptive message")
        
        prompt_parts.extend([
            "",
            "IMPORTANT:",
            "- Only modify files related to the target service",
            "- Use clear, descriptive commit messages",
            "- Do not delete any critical resources",
            f"- Working directory: {self.git_repo_path}",
        ])
        
        return "\n".join(prompt_parts)
    
    @safe_execution
    def _execute_with_cli(self, plan_context: str) -> dict:
        """
        Execute the plan via Gemini CLI.
        
        Uses validated CLI pattern with --non-interactive.
        """
        cmd = [
            "gemini",
            "--non-interactive",
            "--output-format", "json",
        ]
        
        # Add auto-approve flag if enabled (for trusted environments)
        if self.auto_approve:
            cmd.append("--yolo")
        
        cmd.extend(["--prompt", plan_context])
        
        # Environment for Vertex AI mode
        env = {
            **os.environ,
            "GOOGLE_GENAI_USE_VERTEXAI": "true",
        }
        
        logger.info(f"Executing Gemini CLI: {' '.join(cmd[:4])}...")
        
        if self.dry_run:
            logger.info("DRY RUN: Would execute CLI command")
            return {
                "status": "dry_run",
                "command": cmd,
                "message": "Dry run - no actual execution",
            }
        
        try:
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                cwd=self.git_repo_path,
            )
            
            if result.returncode != 0:
                logger.error(f"CLI failed with code {result.returncode}: {result.stderr}")
                return {
                    "status": "failed",
                    "exit_code": result.returncode,
                    "stderr": result.stderr,
                    "stdout": result.stdout,
                }
            
            # Parse JSON output
            try:
                output = json.loads(result.stdout)
            except json.JSONDecodeError:
                output = {"raw_output": result.stdout}
            
            logger.info("CLI execution completed successfully")
            
            return {
                "status": "success",
                "exit_code": result.returncode,
                "output": output,
            }
        
        except subprocess.TimeoutExpired:
            logger.error("CLI execution timed out")
            return {
                "status": "timeout",
                "message": "Execution timed out after 5 minutes",
            }
        
        except FileNotFoundError:
            logger.error("Gemini CLI not found. Is @google/gemini-cli installed?")
            return {
                "status": "error",
                "message": "Gemini CLI not found. Install with: npm install -g @google/gemini-cli",
            }
        
        except Exception as e:
            logger.error(f"CLI execution error: {e}")
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
        
        # Build the prompt
        prompt = self._build_prompt(plan)
        
        # Execute via CLI (with safety check)
        try:
            result = self._execute_with_cli(prompt)
            
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
