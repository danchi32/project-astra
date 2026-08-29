"""Connection-string normalisation.

These cases are all real strings the Neon console produces. The point of the tests is
that an operator can paste one without editing it — the failure they prevent
(`TypeError: connect() got an unexpected keyword argument 'sslmode'`) surfaces at first
connection and looks like a driver bug rather than a copy-paste artefact.
"""
import pytest

from app.core.config import Settings


def _url(raw: str) -> str:
    return Settings(database_url=raw).database_url  # type: ignore[call-arg]


def test_rewrites_the_postgresql_scheme_to_asyncpg():
    assert _url("postgresql://u:p@host/db").startswith("postgresql+asyncpg://")


def test_rewrites_the_short_postgres_scheme_too():
    """Some Neon copy buttons and most ORMs emit `postgres://`."""
    assert _url("postgres://u:p@host/db").startswith("postgresql+asyncpg://")


def test_normalises_a_verbatim_neon_connection_string():
    raw = (
        "postgresql://astra:secret@ep-cool-name-a1b2c3.ap-southeast-1.aws.neon.tech"
        "/astra_marketing?sslmode=require&channel_binding=require"
    )
    result = _url(raw)

    assert result.startswith("postgresql+asyncpg://")
    # asyncpg spells it `ssl`, and TLS must survive the rewrite — a lead database is not
    # something to reach in the clear.
    assert "ssl=require" in result
    assert "sslmode=" not in result
    # asyncpg has no channel_binding parameter; passing it through is a TypeError.
    assert "channel_binding" not in result
    assert "ep-cool-name-a1b2c3.ap-southeast-1.aws.neon.tech/astra_marketing" in result


def test_keeps_query_parameters_it_does_not_recognise():
    """Only the two known-bad parameters are touched; anything else is the operator's."""
    result = _url("postgresql://u:p@host/db?application_name=astra-mkt&sslmode=require")

    assert "application_name=astra-mkt" in result
    assert "ssl=require" in result


def test_drops_the_question_mark_when_nothing_survives():
    result = _url("postgresql://u:p@host/db?channel_binding=require")

    assert result == "postgresql+asyncpg://u:p@host/db"


def test_leaves_sqlite_urls_alone():
    """The test suite and any local demo run on SQLite; none of this applies."""
    assert _url("sqlite+aiosqlite:///:memory:") == "sqlite+aiosqlite:///:memory:"


@pytest.mark.parametrize("raw", ["postgresql://u:p@host/db", "postgres://u:p@host/db"])
def test_leaves_a_bare_url_without_a_query_string_alone(raw: str):
    assert _url(raw) == "postgresql+asyncpg://u:p@host/db"


def test_migration_url_uses_the_direct_endpoint():
    """The pooled string is the right one to paste; DDL still must not run through it."""
    settings = Settings(  # type: ignore[call-arg]
        database_url=(
            "postgresql://u:p@ep-quiet-king-b3pqae1i-pooler.c-4.ap-southeast-1"
            ".aws.neon.tech/astra_marketing?sslmode=require&channel_binding=require"
        )
    )

    assert "-pooler." in settings.database_url
    assert "-pooler." not in settings.migration_database_url
    assert (
        "ep-quiet-king-b3pqae1i.c-4.ap-southeast-1.aws.neon.tech/astra_marketing"
        in settings.migration_database_url
    )
    # The query-string normalisation still applies on the migration path.
    assert "ssl=require" in settings.migration_database_url
    assert "channel_binding" not in settings.migration_database_url


def test_migration_url_is_unchanged_when_already_direct():
    settings = Settings(  # type: ignore[call-arg]
        database_url="postgresql://u:p@ep-quiet-king.ap-southeast-1.aws.neon.tech/db"
    )
    assert settings.migration_database_url == settings.database_url
