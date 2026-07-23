"""Funding network traversal built on top of the repository layer."""

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ngo_tracker.db import Entity, Funding
from ngo_tracker.errors import NotFoundError, ValidationError
from ngo_tracker.repository import get_edges_for, get_summaries
from ngo_tracker.schemas import NetworkGraph

MAX_DEPTH = 4
MAX_NODES = 300


def build_network(session: Session, root_id: int, depth: int = 2, max_nodes: int = MAX_NODES) -> NetworkGraph:
    """Expand the funding network around an entity via breadth-first traversal.

    Follows funding edges in both directions (funders and recipients) up to
    the requested depth, capping total nodes to keep payloads renderable.

    Args:
        session: Active database session.
        root_id: Entity to expand from.
        depth: Hops to traverse (1..MAX_DEPTH).
        max_nodes: Hard cap on nodes included in the result.

    Returns:
        Graph of nodes and cited funding edges around the root.

    Raises:
        ValidationError: If depth is out of range.
        NotFoundError: If the root entity does not exist.
    """
    if not 1 <= depth <= MAX_DEPTH:
        raise ValidationError(f"depth must be between 1 and {MAX_DEPTH}.")
    if session.get(Entity, root_id) is None:
        raise NotFoundError(f"Entity {root_id} not found.")

    visited: set[int] = {root_id}
    frontier: set[int] = {root_id}
    truncated = False

    for _ in range(depth):
        if not frontier:
            break
        rows = session.execute(
            select(Funding.source_id, Funding.target_id).where(
                or_(Funding.source_id.in_(frontier), Funding.target_id.in_(frontier))
            )
        ).all()
        neighbors = {n for src, tgt in rows for n in (src, tgt)} - visited
        if len(visited) + len(neighbors) > max_nodes:
            neighbors = set(sorted(neighbors)[: max_nodes - len(visited)])
            truncated = True
        visited |= neighbors
        frontier = neighbors
        if truncated:
            break

    edges = [
        e for e in get_edges_for(session, visited) if e.source_id in visited and e.target_id in visited
    ]
    return NetworkGraph(
        root_id=root_id,
        nodes=get_summaries(session, visited),
        edges=edges,
        depth=depth,
        truncated=truncated,
    )
