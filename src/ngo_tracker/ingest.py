"""Ingestion adapter for the ProPublica Nonprofit Explorer public API.

Pulls US-registered nonprofit organizations (IRS Form 990 filers) so the
entity catalog can be expanded beyond the seed dataset. Grant-level edges
from 990 Schedule I data can be layered on later; this adapter establishes
the external I/O pattern: timeouts, bounded retries, and typed errors.
"""

import logging
import random
import time

import httpx
from sqlalchemy.orm import Session

from ngo_tracker.errors import ExternalServiceError
from ngo_tracker.repository import upsert_entity

logger = logging.getLogger(__name__)

API_BASE = "https://projects.propublica.org/nonprofits/api/v2"
TIMEOUT = httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0)
MAX_RETRIES = 3
RETRYABLE_STATUS = {429, 502, 503, 504}


def fetch_nonprofits(query: str, client: httpx.Client | None = None) -> list[dict]:
    """Search ProPublica Nonprofit Explorer for organizations.

    Args:
        query: Organization name search string.
        client: Optional injected HTTP client (used by tests).

    Returns:
        Raw organization records from the API.

    Raises:
        ExternalServiceError: If the API is unreachable or keeps failing
            after bounded retries.
    """
    owns_client = client is None
    client = client or httpx.Client(timeout=TIMEOUT)
    try:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = client.get(f"{API_BASE}/search.json", params={"q": query})
            except httpx.TransportError as exc:
                if attempt == MAX_RETRIES:
                    raise ExternalServiceError(
                        "Nonprofit data provider unreachable.", retryable=True
                    ) from exc
                _backoff(attempt)
                continue
            if response.status_code in RETRYABLE_STATUS:
                if attempt == MAX_RETRIES:
                    raise ExternalServiceError(
                        "Nonprofit data provider is temporarily unavailable.", retryable=True
                    )
                _backoff(attempt)
                continue
            if response.status_code != 200:
                raise ExternalServiceError(
                    f"Nonprofit data provider returned status {response.status_code}."
                )
            return response.json().get("organizations", [])
        raise ExternalServiceError("Nonprofit data provider retries exhausted.", retryable=True)
    finally:
        if owns_client:
            client.close()


def ingest_nonprofits(session: Session, query: str, client: httpx.Client | None = None) -> int:
    """Fetch nonprofits matching a query and upsert them as NGO entities.

    Args:
        session: Active database session.
        query: Organization name search string.
        client: Optional injected HTTP client (used by tests).

    Returns:
        Number of organizations processed.

    Raises:
        ExternalServiceError: Propagated from the fetch layer.
    """
    organizations = fetch_nonprofits(query, client=client)
    count = 0
    for org in organizations:
        name = org.get("name")
        if not name:
            continue
        upsert_entity(
            session,
            name=name.title(),
            type="ngo",
            country="United States",
            ein=str(org["ein"]) if org.get("ein") else None,
            description=None,
        )
        count += 1
    logger.info("ingested_nonprofits", extra={"query": query, "count": count})
    return count


def _backoff(attempt: int) -> None:
    """Sleep with exponential backoff and jitter before a retry."""
    time.sleep(min(2**attempt, 8) * (0.5 + random.random() / 2))
