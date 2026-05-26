from nba_data.db.models import RawPage, ScraperRequest, ScraperRun


def test_raw_timestamp_metadata_matches_existing_nullable_migration() -> None:
    assert RawPage.__table__.c.fetched_at.nullable is True
    assert ScraperRequest.__table__.c.requested_at.nullable is True
    assert ScraperRun.__table__.c.started_at.nullable is True

    assert RawPage.__table__.c.fetched_at.server_default is not None
    assert ScraperRequest.__table__.c.requested_at.server_default is not None
    assert ScraperRun.__table__.c.started_at.server_default is not None
