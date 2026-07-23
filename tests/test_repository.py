"""Repository layer tests: search, totals, upserts, validation."""

import pytest

from ngo_tracker.errors import NotFoundError
from ngo_tracker.repository import (
    add_funding,
    get_entity_detail,
    search_entities,
    upsert_entity,
)


def test_search_matches_substring_case_insensitive(seeded_session):
    results, total = search_entities(seeded_session, "gates")
    names = [r.name for r in results]
    assert total >= 2
    assert any("Gates Foundation" in n for n in names)
    assert any(n == "Bill Gates" for n in names)


def test_search_type_filter(seeded_session):
    results, _ = search_entities(seeded_session, "gates", entity_type="person")
    assert all(r.type == "person" for r in results)
    assert len(results) == 1


def test_entity_detail_totals(seeded_session):
    results, _ = search_entities(seeded_session, "Open Society")
    detail = get_entity_detail(seeded_session, results[0].id)
    assert detail.total_received_usd == pytest.approx(18_000_000_000)
    assert detail.total_funded_usd == pytest.approx(103_000_000)


def test_entity_detail_not_found(seeded_session):
    with pytest.raises(NotFoundError):
        get_entity_detail(seeded_session, 999_999)


def test_upsert_dedup_by_name_and_type(session):
    first = upsert_entity(session, name="Test NGO", type="ngo")
    second = upsert_entity(session, name="Test NGO", type="ngo")
    assert first.id == second.id


def test_upsert_dedup_by_ein(session):
    first = upsert_entity(session, name="Old Name", type="ngo", ein="12-345")
    second = upsert_entity(session, name="New Name", type="ngo", ein="12-345")
    assert first.id == second.id


def test_upsert_rejects_unknown_type(session):
    with pytest.raises(ValueError, match="Unknown entity type"):
        upsert_entity(session, name="X", type="cartel")


def test_add_funding_requires_positive_amount_and_citation(session):
    funder = upsert_entity(session, name="A", type="foundation")
    recipient = upsert_entity(session, name="B", type="ngo")
    with pytest.raises(ValueError, match="positive"):
        add_funding(
            session, source_id=funder.id, target_id=recipient.id,
            amount_usd=0, year=2024, citation="https://example.org",
        )
    with pytest.raises(ValueError, match="citation"):
        add_funding(
            session, source_id=funder.id, target_id=recipient.id,
            amount_usd=100, year=2024, citation="  ",
        )
