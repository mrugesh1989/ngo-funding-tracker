"""Demo dataset of publicly documented funding relationships.

Every edge cites a public source (annual reports, IRS Form 990 filings, or
official grant databases). The seed exists so the product works end-to-end
before large-scale ingestion is wired up.
"""

from sqlalchemy.orm import Session

from ngo_tracker.repository import add_funding, upsert_entity

_ENTITIES = [
    ("Bill & Melinda Gates Foundation", "foundation", "United States", "Private foundation focused on global health and development."),
    ("Open Society Foundations", "foundation", "United States", "Grantmaking network founded by George Soros supporting civil society."),
    ("Ford Foundation", "foundation", "United States", "Private foundation advancing human welfare."),
    ("Gavi, the Vaccine Alliance", "ngo", "Switzerland", "Public-private partnership improving vaccine access."),
    ("Human Rights Watch", "ngo", "United States", "International human rights research and advocacy organization."),
    ("Amnesty International", "ngo", "United Kingdom", "Global human rights movement."),
    ("World Health Organization", "government", "Switzerland", "United Nations specialized agency for public health."),
    ("Bill Gates", "person", "United States", "Co-chair of the Bill & Melinda Gates Foundation."),
    ("George Soros", "person", "United States", "Founder and chair of the Open Society Foundations."),
    ("PATH", "ngo", "United States", "Global health nonprofit developing health technologies."),
    ("Rockefeller Foundation", "foundation", "United States", "Private foundation promoting the well-being of humanity."),
    ("Doctors Without Borders (MSF)", "ngo", "France", "International medical humanitarian organization."),
]

# (source name, target name, amount USD, year, purpose, citation)
_EDGES = [
    ("Bill Gates", "Bill & Melinda Gates Foundation", 20_000_000_000, 2022,
     "Endowment contribution", "https://www.gatesfoundation.org/ideas/media-center/press-releases"),
    ("Bill & Melinda Gates Foundation", "Gavi, the Vaccine Alliance", 1_600_000_000, 2020,
     "Vaccine access 2021-2025 pledge", "https://www.gavi.org/investing-gavi/funding/donor-profiles"),
    ("Bill & Melinda Gates Foundation", "World Health Organization", 250_000_000, 2020,
     "COVID-19 response", "https://www.who.int/about/funding/contributors"),
    ("Bill & Melinda Gates Foundation", "PATH", 150_000_000, 2021,
     "Global health innovation", "https://www.gatesfoundation.org/about/committed-grants"),
    ("George Soros", "Open Society Foundations", 18_000_000_000, 2017,
     "Endowment transfer", "https://www.opensocietyfoundations.org/newsroom"),
    ("Open Society Foundations", "Human Rights Watch", 100_000_000, 2010,
     "Ten-year general support grant", "https://www.hrw.org/news/2010/09/07"),
    ("Open Society Foundations", "Amnesty International", 3_000_000, 2019,
     "Human rights programs", "https://www.opensocietyfoundations.org/grants/past"),
    ("Ford Foundation", "Human Rights Watch", 10_000_000, 2018,
     "General support", "https://www.fordfoundation.org/work/our-grants/awarded-grants/"),
    ("Rockefeller Foundation", "World Health Organization", 15_000_000, 2021,
     "Pandemic preparedness", "https://www.rockefellerfoundation.org/grants/"),
    ("Rockefeller Foundation", "PATH", 5_000_000, 2019,
     "Health systems", "https://www.rockefellerfoundation.org/grants/"),
    ("Ford Foundation", "Doctors Without Borders (MSF)", 2_000_000, 2020,
     "Emergency response", "https://www.fordfoundation.org/work/our-grants/awarded-grants/"),
]


def seed_demo_data(session: Session) -> int:
    """Populate the database with the cited demo dataset.

    Idempotent: entities are deduplicated by (name, type); edges are only
    inserted when the funding table is empty.

    Args:
        session: Active database session.

    Returns:
        Number of funding edges inserted (0 if already seeded).
    """
    from ngo_tracker.db import Funding

    ids: dict[str, int] = {}
    for name, type_, country, description in _ENTITIES:
        entity = upsert_entity(session, name=name, type=type_, country=country, description=description)
        ids[name] = entity.id

    if session.query(Funding).count() > 0:
        return 0

    for source, target, amount, year, purpose, citation in _EDGES:
        add_funding(
            session,
            source_id=ids[source],
            target_id=ids[target],
            amount_usd=amount,
            year=year,
            purpose=purpose,
            citation=citation,
        )
    return len(_EDGES)
