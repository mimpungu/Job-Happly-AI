"""Les index annoncés (requêtes de recherche, déduplication, suivi) existent réellement."""

import pytest
from sqlalchemy import create_engine, inspect

from app.core.database.session import to_driver_url

INDEX_ATTENDUS = {
    "job_offer_sources": {"uq_job_offer_sources_owner_id_source_id_external_id"},
    "job_offers": {
        "ix_job_offers_owner_id_country_code",
        "ix_job_offers_owner_id_published_at",
        "ix_job_offers_owner_id_title_lower",
        "ix_job_offers_owner_id_company_lower",
        "ix_job_offers_owner_id_status",
        "ix_job_offers_owner_id_content_hash",
        "uq_job_offers_owner_id_canonical_url",
    },
    "applications": {"ix_applications_owner_id_status", "uq_applications_owner_id_offer_id"},
    "search_runs": {"ix_search_runs_owner_id_started_at"},
    "ai_usages": {"ix_ai_usages_owner_id_created_at"},
    "job_analyses": {"uq_job_analyses_reuse_key"},
}


@pytest.mark.parametrize("table", sorted(INDEX_ATTENDUS))
def test_les_index_attendus_existent(schema_migre: str, table: str) -> None:
    engine = create_engine(to_driver_url(schema_migre))
    try:
        presents = {i["name"] for i in inspect(engine).get_indexes(table)}
    finally:
        engine.dispose()

    assert INDEX_ATTENDUS[table] <= presents
