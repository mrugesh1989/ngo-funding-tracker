"""API boundary tests: contracts, error mapping, plan enforcement."""

from ngo_tracker.plans import DEMO_PRO_KEY

PRO_HEADERS = {"X-API-Key": DEMO_PRO_KEY}


def _first_id(client, query):
    return client.get("/api/search", params={"q": query}).json()["results"][0]["id"]


def test_search_returns_results(client):
    response = client.get("/api/search", params={"q": "gates"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 2
    assert {"id", "name", "type", "country"} <= set(body["results"][0].keys())


def test_search_query_too_short_is_422(client):
    assert client.get("/api/search", params={"q": "a"}).status_code == 422


def test_entity_detail_and_404_mapping(client):
    entity_id = _first_id(client, "Human Rights Watch")
    detail = client.get(f"/api/entities/{entity_id}")
    assert detail.status_code == 200
    assert detail.json()["total_received_usd"] > 0

    missing = client.get("/api/entities/999999")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"


def test_network_free_depth_allowed(client):
    entity_id = _first_id(client, "Bill Gates")
    response = client.get(f"/api/entities/{entity_id}/network", params={"depth": 2})
    assert response.status_code == 200
    body = response.json()
    assert body["root_id"] == entity_id
    assert len(body["nodes"]) > 1
    assert all(edge["citation"] for edge in body["edges"])


def test_network_deep_requires_pro(client):
    entity_id = _first_id(client, "Bill Gates")
    denied = client.get(f"/api/entities/{entity_id}/network", params={"depth": 3})
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "forbidden"

    allowed = client.get(
        f"/api/entities/{entity_id}/network", params={"depth": 3}, headers=PRO_HEADERS
    )
    assert allowed.status_code == 200


def test_unknown_api_key_falls_back_to_free(client):
    entity_id = _first_id(client, "Bill Gates")
    response = client.get(
        f"/api/entities/{entity_id}/network",
        params={"depth": 3},
        headers={"X-API-Key": "not-a-real-key"},
    )
    assert response.status_code == 403


def test_export_requires_pro(client):
    entity_id = _first_id(client, "Ford Foundation")
    assert client.get(f"/api/entities/{entity_id}/export.csv").status_code == 403

    response = client.get(f"/api/entities/{entity_id}/export.csv", headers=PRO_HEADERS)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    lines = response.text.strip().splitlines()
    assert lines[0] == "funder,recipient,amount_usd,year,purpose,citation"
    assert len(lines) > 1


def test_plans_metadata(client):
    response = client.get("/api/plans")
    assert response.status_code == 200
    plans = {p["plan"]: p for p in response.json()}
    assert plans["free"]["max_depth"] == 2
    assert plans["pro"]["export"] is True
