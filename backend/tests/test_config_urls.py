"""public_app_url must normalize to an origin so redirects (/billing, /reset-password)
don't end up as /login/billing etc."""
import pytest

from app.core.config import Settings


def _settings(app_url: str) -> Settings:
    return Settings(jwt_secret_key="x", database_url="sqlite+aiosqlite:///:memory:",
                    public_app_url=app_url)


@pytest.mark.parametrize("given,expected", [
    ("https://astra.technomateai.com/login", "https://astra.technomateai.com"),
    ("https://astra.technomateai.com/", "https://astra.technomateai.com"),
    ("https://astra.technomateai.com", "https://astra.technomateai.com"),
    ("https://astra.technomateai.com/dashboard?x=1", "https://astra.technomateai.com"),
    ("http://localhost:3000", "http://localhost:3000"),
])
def test_public_app_url_normalized_to_origin(given, expected):
    assert _settings(given).public_app_url == expected
    # And a built redirect is correct, not doubled up.
    base = _settings(given).public_app_url
    assert f"{base}/billing?checkout=cancelled".endswith("com/billing?checkout=cancelled") or "localhost" in base
