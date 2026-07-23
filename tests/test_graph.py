"""Graph traversal tests: depth behavior, truncation, validation."""

import pytest

from ngo_tracker.errors import NotFoundError, ValidationError
from ngo_tracker.graph import build_network
from ngo_tracker.repository import add_funding, search_entities, upsert_entity


def _root_id(session, name):
    results, _ = search_entities(session, name)
    return results[0].id


def test_depth_one_returns_direct_neighbors_only(seeded_session):
    root = _root_id(seeded_session, "Bill Gates")
    network = build_network(seeded_session, root, depth=1)
    names = {n.name for n in network.nodes}
    assert "Bill & Melinda Gates Foundation" in names
    # Gavi is two hops from Bill Gates.
    assert "Gavi, the Vaccine Alliance" not in names


def test_depth_two_expands_further(seeded_session):
    root = _root_id(seeded_session, "Bill Gates")
    network = build_network(seeded_session, root, depth=2)
    names = {n.name for n in network.nodes}
    assert "Gavi, the Vaccine Alliance" in names
    assert all(e.citation for e in network.edges)


def test_invalid_depth_raises(seeded_session):
    root = _root_id(seeded_session, "Bill Gates")
    with pytest.raises(ValidationError):
        build_network(seeded_session, root, depth=0)
    with pytest.raises(ValidationError):
        build_network(seeded_session, root, depth=5)


def test_missing_root_raises(seeded_session):
    with pytest.raises(NotFoundError):
        build_network(seeded_session, 999_999, depth=1)


def test_node_cap_truncates(session):
    hub = upsert_entity(session, name="Hub Foundation", type="foundation")
    for i in range(10):
        spoke = upsert_entity(session, name=f"Spoke {i}", type="ngo")
        add_funding(
            session, source_id=hub.id, target_id=spoke.id,
            amount_usd=1000, year=2024, citation="https://example.org/grant",
        )
    network = build_network(session, hub.id, depth=1, max_nodes=5)
    assert network.truncated is True
    assert len(network.nodes) == 5
