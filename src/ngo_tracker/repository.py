"""Data access layer for entities and funding relationships."""

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ngo_tracker.db import Entity, Funding
from ngo_tracker.errors import NotFoundError
from ngo_tracker.schemas import EntityDetail, EntitySummary, FundingEdge

VALID_ENTITY_TYPES = {"ngo", "foundation", "person", "government", "corporation"}


def _to_summary(entity: Entity) -> EntitySummary:
    """Convert an ORM entity to its API summary form."""
    return EntitySummary(id=entity.id, name=entity.name, type=entity.type, country=entity.country)


def search_entities(
    session: Session, query: str, entity_type: str | None = None, limit: int = 25
) -> tuple[list[EntitySummary], int]:
    """Search entities by name substring, optionally filtered by type.

    Args:
        session: Active database session.
        query: Case-insensitive name fragment.
        entity_type: Optional filter (ngo, foundation, person, government, corporation).
        limit: Maximum results returned.

    Returns:
        Tuple of (matching summaries ordered by name, total match count).
    """
    stmt = select(Entity).where(Entity.name.ilike(f"%{query}%"))
    count_stmt = select(func.count()).select_from(Entity).where(Entity.name.ilike(f"%{query}%"))
    if entity_type:
        stmt = stmt.where(Entity.type == entity_type)
        count_stmt = count_stmt.where(Entity.type == entity_type)
    total = session.execute(count_stmt).scalar_one()
    rows = session.execute(stmt.order_by(Entity.name).limit(limit)).scalars().all()
    return [_to_summary(e) for e in rows], total


def get_entity_detail(session: Session, entity_id: int) -> EntityDetail:
    """Load one entity with funding totals.

    Args:
        session: Active database session.
        entity_id: Entity primary key.

    Returns:
        Full entity detail including aggregate funded/received totals.

    Raises:
        NotFoundError: If no entity exists with the given id.
    """
    entity = session.get(Entity, entity_id)
    if entity is None:
        raise NotFoundError(f"Entity {entity_id} not found.")
    funded = session.execute(
        select(func.coalesce(func.sum(Funding.amount_usd), 0.0)).where(Funding.source_id == entity_id)
    ).scalar_one()
    received = session.execute(
        select(func.coalesce(func.sum(Funding.amount_usd), 0.0)).where(Funding.target_id == entity_id)
    ).scalar_one()
    return EntityDetail(
        id=entity.id,
        name=entity.name,
        type=entity.type,
        country=entity.country,
        ein=entity.ein,
        description=entity.description,
        total_funded_usd=float(funded),
        total_received_usd=float(received),
    )


def get_edges_for(session: Session, entity_ids: set[int]) -> list[FundingEdge]:
    """Return all funding edges touching any of the given entities."""
    rows = session.execute(
        select(Funding).where(or_(Funding.source_id.in_(entity_ids), Funding.target_id.in_(entity_ids)))
    ).scalars().all()
    return [
        FundingEdge(
            source_id=f.source_id,
            target_id=f.target_id,
            amount_usd=f.amount_usd,
            year=f.year,
            purpose=f.purpose,
            citation=f.citation,
        )
        for f in rows
    ]


def get_summaries(session: Session, entity_ids: set[int]) -> list[EntitySummary]:
    """Return summaries for the given entity ids."""
    rows = session.execute(select(Entity).where(Entity.id.in_(entity_ids))).scalars().all()
    return [_to_summary(e) for e in rows]


def upsert_entity(
    session: Session,
    *,
    name: str,
    type: str,
    country: str | None = None,
    ein: str | None = None,
    description: str | None = None,
) -> Entity:
    """Insert an entity or return the existing one matched by EIN or (name, type).

    Args:
        session: Active database session.
        name: Entity display name.
        type: One of VALID_ENTITY_TYPES.
        country: Optional country name.
        ein: Optional IRS EIN used as the primary dedup key.
        description: Optional public description.

    Returns:
        The persisted entity (flushed, id populated).

    Raises:
        ValueError: If the entity type is not recognized.
    """
    if type not in VALID_ENTITY_TYPES:
        raise ValueError(f"Unknown entity type: {type!r}")
    existing = None
    if ein:
        existing = session.execute(select(Entity).where(Entity.ein == ein)).scalar_one_or_none()
    if existing is None:
        existing = session.execute(
            select(Entity).where(Entity.name == name, Entity.type == type)
        ).scalar_one_or_none()
    if existing is not None:
        return existing
    entity = Entity(name=name, type=type, country=country, ein=ein, description=description)
    session.add(entity)
    session.flush()
    return entity


def add_funding(
    session: Session,
    *,
    source_id: int,
    target_id: int,
    amount_usd: float,
    year: int,
    citation: str,
    purpose: str | None = None,
) -> Funding:
    """Record a documented funding edge.

    Raises:
        ValueError: If the amount is not positive or the citation is empty.
    """
    if amount_usd <= 0:
        raise ValueError("Funding amount must be positive.")
    if not citation.strip():
        raise ValueError("Every funding edge requires a public citation.")
    funding = Funding(
        source_id=source_id,
        target_id=target_id,
        amount_usd=amount_usd,
        year=year,
        purpose=purpose,
        citation=citation,
    )
    session.add(funding)
    session.flush()
    return funding
