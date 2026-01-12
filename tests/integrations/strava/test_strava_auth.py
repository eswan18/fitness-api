from fitness.integrations.strava.auth import build_oauth_authorize_url


def test_build_oauth_authorize_url(monkeypatch):
    monkeypatch.setattr("fitness.integrations.strava.auth.CLIENT_ID", "123")
    monkeypatch.setattr(
        "fitness.integrations.strava.auth.OAUTH_URL",
        "https://www.fakestrava.com/oauth/authorize",
    )
    url = build_oauth_authorize_url("https://examplecallback.com")
    assert (
        url
        == "https://www.fakestrava.com/oauth/authorize?client_id=123&redirect_uri=https%3A%2F%2Fexamplecallback.com&scope=activity%3Aread_all&response_type=code"
    )
