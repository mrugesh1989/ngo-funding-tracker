"""Shared fixtures: in-memory database sessions and a seeded API client."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from ngo_tracker.db import make_engine
from ngo_tracker.main import create_app
from ngo_tracker.seed import seed_demo_data


@pytest.fixture()
def session():
    """Yield a session bound to a fresh in-memory database."""
    engine = make_engine(":memory:")
    factory = sessionmaker(bind=engine, future=True)
    sess = factory()
    yield sess
    sess.close()
    engine.dispose()


@pytest.fixture()
def seeded_session(session):
    """Yield a session pre-populated with the demo dataset."""
    seed_demo_data(session)
    session.commit()
    return session


@pytest.fixture()
def client():
    """Yield a test client for the app backed by an in-memory database."""
    app = create_app(":memory:")
    with TestClient(app) as test_client:
        yield test_client
