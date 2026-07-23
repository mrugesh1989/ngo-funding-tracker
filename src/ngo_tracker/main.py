"""FastAPI application: HTTP boundary for the NGO funding tracker."""

import csv
import io
import logging
import os
from collections.abc import Iterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, Query, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session, sessionmaker

from ngo_tracker.db import DEFAULT_DB_PATH, make_engine
from ngo_tracker.errors import AppError
from ngo_tracker.graph import build_network
from ngo_tracker.plans import Plan, check_depth, check_export, plans_metadata, resolve_plan, seed_demo_key
from ngo_tracker.repository import VALID_ENTITY_TYPES, get_entity_detail, search_entities
from ngo_tracker.schemas import EntityDetail, NetworkGraph, SearchResults
from ngo_tracker.seed import seed_demo_data

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "static"


def create_app(db_path: Path | str = DEFAULT_DB_PATH) -> FastAPI:
    """Build the FastAPI app bound to a database.

    Args:
        db_path: SQLite file path, or ":memory:" for tests.

    Returns:
        Configured application with routes, error handling, and static files.
    """
    engine = make_engine(db_path)
    factory = sessionmaker(bind=engine, future=True)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        session = factory()
        try:
            seed_demo_data(session)
            seed_demo_key(session)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
        yield

    app = FastAPI(title="NGO Funding Tracker", version="0.1.0", lifespan=lifespan)
    app.state.session_factory = factory

    def get_session() -> Iterator[Session]:
        """Yield a request-scoped database session."""
        session = factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_plan(
        session: Session = Depends(get_session),
        x_api_key: str | None = Header(default=None),
    ) -> Plan:
        """Resolve the caller's plan from the X-API-Key header."""
        return resolve_plan(session, x_api_key)

    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        """Map domain errors to their HTTP status with a stable envelope."""
        if exc.status >= 500:
            logger.exception("app_error", extra={"code": exc.code})
            message = "The request could not be completed."
        else:
            logger.warning("app_error", extra={"code": exc.code, "detail": str(exc)})
            message = str(exc)
        return JSONResponse(status_code=exc.status, content={"error": {"code": exc.code, "message": message}})

    @app.get("/api/search", response_model=SearchResults)
    def search(
        q: str = Query(min_length=2, max_length=200),
        type: str | None = Query(default=None),
        session: Session = Depends(get_session),
    ) -> SearchResults:
        """Search entities by name, optionally filtered by type."""
        entity_type = type if type in VALID_ENTITY_TYPES else None
        results, total = search_entities(session, q.strip(), entity_type)
        return SearchResults(query=q.strip(), results=results, total=total)

    @app.get("/api/entities/{entity_id}", response_model=EntityDetail)
    def entity_detail(entity_id: int, session: Session = Depends(get_session)) -> EntityDetail:
        """Return one entity with funding totals."""
        return get_entity_detail(session, entity_id)

    @app.get("/api/entities/{entity_id}/network", response_model=NetworkGraph)
    def entity_network(
        entity_id: int,
        depth: int = Query(default=2, ge=1, le=4),
        session: Session = Depends(get_session),
        plan: Plan = Depends(get_plan),
    ) -> NetworkGraph:
        """Return the funding network around an entity; deep traversal is pro-only."""
        check_depth(plan, depth)
        return build_network(session, entity_id, depth=depth)

    @app.get("/api/entities/{entity_id}/export.csv")
    def export_csv(
        entity_id: int,
        depth: int = Query(default=2, ge=1, le=4),
        session: Session = Depends(get_session),
        plan: Plan = Depends(get_plan),
    ) -> StreamingResponse:
        """Export the entity's funding network as CSV (pro plan only)."""
        check_export(plan)
        check_depth(plan, depth)
        network = build_network(session, entity_id, depth=depth)
        names = {node.id: node.name for node in network.nodes}
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["funder", "recipient", "amount_usd", "year", "purpose", "citation"])
        for edge in network.edges:
            writer.writerow(
                [names[edge.source_id], names[edge.target_id], edge.amount_usd, edge.year,
                 edge.purpose or "", edge.citation]
            )
        buffer.seek(0)
        return StreamingResponse(
            iter([buffer.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="network_{entity_id}.csv"'},
        )

    @app.get("/api/plans")
    def plans() -> list[dict]:
        """Return pricing metadata for the UI."""
        return plans_metadata()

    if STATIC_DIR.is_dir():
        @app.get("/", include_in_schema=False)
        def index() -> FileResponse:
            """Serve the single-page frontend."""
            return FileResponse(STATIC_DIR / "index.html")

        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    return app


# NGO_TRACKER_DB lets hosts (e.g. Render) point SQLite at a mounted disk.
app = create_app(os.environ.get("NGO_TRACKER_DB", DEFAULT_DB_PATH))
