"""Runtime configuration.

All values are read from environment variables *at call time* (not import time) so that
tests can set them via fixtures/monkeypatch after the module is imported.
"""
from __future__ import annotations

import os


# --- DynamoDB table names ---------------------------------------------------------
def findings_table() -> str:
    return os.environ.get("FINDINGS_TABLE", "CostKiller-Findings")


def accounts_table() -> str:
    return os.environ.get("ACCOUNTS_TABLE", "CostKiller-Accounts")


def execution_log_table() -> str:
    return os.environ.get("EXECUTION_LOG_TABLE", "CostKiller-ExecutionLog")


def pricing_table() -> str:
    return os.environ.get("PRICING_TABLE", "CostKiller-PricingMatrix")


# --- Cross-account role configuration ---------------------------------------------
def scan_role_name() -> str:
    return os.environ.get("SCAN_ROLE_NAME", "CostKillerScanRole")


def exec_role_name() -> str:
    return os.environ.get("EXEC_ROLE_NAME", "CostKillerExecRole")


def external_id() -> str:
    return os.environ.get("EXTERNAL_ID", "")


# --- Detection thresholds ---------------------------------------------------------
def idle_days_threshold() -> int:
    return int(os.environ.get("IDLE_DAYS_THRESHOLD", "7"))


def default_regions() -> list[str]:
    raw = os.environ.get("DEFAULT_REGIONS", "us-east-1")
    return [r.strip() for r in raw.split(",") if r.strip()]


# --- Guardrails -------------------------------------------------------------------
def protected_tag_keys() -> list[str]:
    """Tag keys whose mere presence (truthy value) protects a resource from deletion."""
    raw = os.environ.get("PROTECTED_TAG_KEYS", "CostKiller:Protect,DoNotDelete")
    return [k.strip() for k in raw.split(",") if k.strip()]


def protected_environments() -> list[str]:
    """Values of an ``Environment`` tag that protect a resource (case-insensitive)."""
    raw = os.environ.get("PROTECTED_ENVIRONMENTS", "prod,production")
    return [v.strip().lower() for v in raw.split(",") if v.strip()]
