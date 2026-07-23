"""Pydantic schemas for the NGO funding tracker API."""

from pydantic import BaseModel, Field

EntityType = str  # one of: ngo, foundation, person, government, corporation


class EntitySummary(BaseModel):
    """Compact entity representation used in search results and graph nodes."""

    id: int = Field(description="Internal entity identifier.")
    name: str = Field(description="Display name of the entity.")
    type: EntityType = Field(description="Entity kind: ngo, foundation, person, government, corporation.")
    country: str | None = Field(default=None, description="ISO-style country name, if known.")


class EntityDetail(EntitySummary):
    """Full entity record including registry identifiers and totals."""

    ein: str | None = Field(default=None, description="US IRS Employer Identification Number, if any.")
    description: str | None = Field(default=None, description="Short public description of the entity.")
    total_funded_usd: float = Field(default=0.0, description="Sum of outgoing documented funding in USD.")
    total_received_usd: float = Field(default=0.0, description="Sum of incoming documented funding in USD.")


class FundingEdge(BaseModel):
    """A single documented funding relationship between two entities."""

    source_id: int = Field(description="Funder entity id.")
    target_id: int = Field(description="Recipient entity id.")
    amount_usd: float = Field(description="Grant or donation amount in USD.")
    year: int = Field(description="Year the funding was reported.")
    purpose: str | None = Field(default=None, description="Stated purpose of the grant, if disclosed.")
    citation: str = Field(description="Public source (URL or filing reference) documenting this edge.")


class NetworkGraph(BaseModel):
    """Graph payload consumed by the frontend visualization."""

    root_id: int = Field(description="Entity the network was expanded from.")
    nodes: list[EntitySummary] = Field(description="Entities present in the network.")
    edges: list[FundingEdge] = Field(description="Documented funding relationships between nodes.")
    depth: int = Field(description="Traversal depth used to build the graph.")
    truncated: bool = Field(default=False, description="True if the node limit cut off the traversal.")


class SearchResults(BaseModel):
    """Paginated search response."""

    query: str = Field(description="Normalized query string that was executed.")
    results: list[EntitySummary] = Field(description="Matching entities ordered by relevance.")
    total: int = Field(description="Total number of matches.")


class ErrorBody(BaseModel):
    """Stable error envelope returned by the API boundary."""

    code: str = Field(description="Machine-readable error code.")
    message: str = Field(description="Human-readable, client-safe message.")
