"""Freemium plan definitions, API-key resolution, and feature gating."""

import hashlib
from enum import Enum

from sqlalchemy import select
from sqlalchemy.orm import Session

from ngo_tracker.db import ApiKey
from ngo_tracker.errors import AuthorizationError


class Plan(str, Enum):
    """Subscription tiers exposed by the product."""

    FREE = "free"
    PRO = "pro"


PLAN_LIMITS: dict[Plan, dict] = {
    Plan.FREE: {"max_depth": 2, "export": False, "price_usd_month": 0},
    Plan.PRO: {"max_depth": 4, "export": True, "price_usd_month": 29},
}

# Deterministic demo key so the pro tier is testable out of the box.
# In production, keys are issued per customer and never committed.
DEMO_PRO_KEY = "demo-pro-key-123"


def hash_key(raw_key: str) -> str:
    """Return the SHA-256 hex digest used to store and look up API keys."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def seed_demo_key(session: Session) -> None:
    """Insert the demo pro API key if it is not already present.

    Args:
        session: Active database session.
    """
    digest = hash_key(DEMO_PRO_KEY)
    existing = session.execute(select(ApiKey).where(ApiKey.key_hash == digest)).scalar_one_or_none()
    if existing is None:
        session.add(ApiKey(key_hash=digest, plan=Plan.PRO.value, label="demo"))
        session.flush()


def resolve_plan(session: Session, raw_key: str | None) -> Plan:
    """Resolve the caller's plan from an optional API key.

    Unknown or missing keys fall back to the free tier rather than erroring,
    so anonymous browsing always works.

    Args:
        session: Active database session.
        raw_key: Value of the X-API-Key header, if provided.

    Returns:
        The plan associated with the key, or FREE.
    """
    if not raw_key:
        return Plan.FREE
    row = session.execute(
        select(ApiKey).where(ApiKey.key_hash == hash_key(raw_key))
    ).scalar_one_or_none()
    if row is None:
        return Plan.FREE
    return Plan(row.plan)


def check_depth(plan: Plan, depth: int) -> None:
    """Ensure the requested traversal depth is allowed for the plan.

    Args:
        plan: Caller's resolved plan.
        depth: Requested network depth.

    Raises:
        AuthorizationError: If the depth exceeds the plan limit.
    """
    limit = PLAN_LIMITS[plan]["max_depth"]
    if depth > limit:
        raise AuthorizationError(
            f"Depth {depth} requires the pro plan (your plan allows up to {limit}). "
            "Pass a valid X-API-Key to unlock deeper networks."
        )


def check_export(plan: Plan) -> None:
    """Ensure the plan permits CSV export.

    Args:
        plan: Caller's resolved plan.

    Raises:
        AuthorizationError: If the plan does not include exports.
    """
    if not PLAN_LIMITS[plan]["export"]:
        raise AuthorizationError("CSV export requires the pro plan. Pass a valid X-API-Key.")


def plans_metadata() -> list[dict]:
    """Return pricing metadata for the UI."""
    return [
        {"plan": plan.value, **limits, "features": _features(limits)}
        for plan, limits in PLAN_LIMITS.items()
    ]


def _features(limits: dict) -> list[str]:
    """Build a human-readable feature list from plan limits."""
    features = [f"Network depth up to {limits['max_depth']}"]
    features.append("CSV export" if limits["export"] else "Search and basic graphs")
    return features
