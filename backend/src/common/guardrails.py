"""Safety guardrails — applied during Discovery AND re-checked at Execution.

A resource is protected (never flagged or deleted) if it is managed by an Auto Scaling
Group, carries a protected tag key, or carries a production ``Environment`` tag.
"""
from __future__ import annotations

from typing import Optional

from common import config

_TRUTHY = {"", "true", "1", "yes", "on"}


def normalize_tags(tags) -> dict:
    """Accept EC2-style ``[{"Key","Value"}]`` or a plain dict; return a plain dict."""
    if isinstance(tags, dict):
        return tags
    return {t["Key"]: t.get("Value", "") for t in (tags or [])}


def is_protected(tags) -> tuple[bool, Optional[str]]:
    """Return ``(protected, reason)``. ``reason`` is None when not protected."""
    tagd = normalize_tags(tags)

    # 1. Auto Scaling Group managed — deleting these breaks capacity / triggers replacement.
    if "aws:autoscaling:groupName" in tagd:
        return True, "auto_scaling_group"

    # 2. Explicit protective tag keys (present with a non-false value).
    for key in config.protected_tag_keys():
        if key in tagd and str(tagd[key]).strip().lower() in _TRUTHY:
            return True, f"protected_tag:{key}"

    # 3. Production environment tag.
    env = tagd.get("Environment") or tagd.get("environment")
    if env and str(env).strip().lower() in config.protected_environments():
        return True, f"protected_environment:{env}"

    return False, None
