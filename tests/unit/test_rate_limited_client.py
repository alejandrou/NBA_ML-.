import httpx
import pytest

from nba_data.config.settings import MINIMUM_SCRAPER_DELAY_SECONDS, Settings
from nba_data.scraping.cache import HtmlCache
from nba_data.scraping.client import BasketballReferenceClient, RateLimitExceededError


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def _settings(**overrides) -> Settings:
    values = {
        "scraper_user_agent": "nba-data-tests/0.1",
        "scraper_min_delay_seconds": MINIMUM_SCRAPER_DELAY_SECONDS,
        "scraper_max_requests_per_minute": 10,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def _unvalidated_settings(**overrides) -> Settings:
    """Settings that never passed the field validators.

    Stands in for a hand-built object, a test stub, or a future field change —
    the cases the limiter's own clamp has to survive.
    """
    return _settings().model_copy(update=overrides)


@pytest.mark.unit
def test_client_sends_user_agent() -> None:
    seen_headers = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers["user-agent"] = request.headers["user-agent"]
        return httpx.Response(200, text="<html>ok</html>")

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = BasketballReferenceClient(_settings(), http_client=http_client, sleeper=lambda _: None)

    assert client.get("https://www.basketball-reference.com/teams/BOS/2024.html") == "<html>ok</html>"
    assert seen_headers["user-agent"] == "nba-data-tests/0.1"


@pytest.mark.unit
def test_client_uses_cache_before_network(tmp_path) -> None:
    cache = HtmlCache(tmp_path)
    url = "https://www.basketball-reference.com/teams/BOS/2024.html"
    cache.set(url, "<html>cached</html>")

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("network should not be called")

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = BasketballReferenceClient(_settings(), cache=cache, http_client=http_client)

    assert client.get(url) == "<html>cached</html>"


@pytest.mark.unit
def test_client_enforces_delay_between_requests() -> None:
    clock = FakeClock()
    responses = iter(["first", "second"])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=next(responses))

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = BasketballReferenceClient(
        _settings(),
        http_client=http_client,
        sleeper=clock.sleep,
        clock=clock,
    )

    assert client.get("https://www.basketball-reference.com/teams/BOS/2024.html") == "first"
    assert client.get("https://www.basketball-reference.com/teams/BOS/2025.html") == "second"
    assert clock.sleeps == [MINIMUM_SCRAPER_DELAY_SECONDS]


@pytest.mark.unit
def test_client_never_sleeps_below_the_floor_for_an_unvalidated_delay() -> None:
    """20 requests/minute alone implies 3 seconds; the floor has to win anyway."""
    clock = FakeClock()
    responses = iter(["first", "second"])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=next(responses))

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = BasketballReferenceClient(
        _unvalidated_settings(
            scraper_min_delay_seconds=0.0,
            scraper_max_requests_per_minute=20,
        ),
        http_client=http_client,
        sleeper=clock.sleep,
        clock=clock,
    )

    assert client.get("https://www.basketball-reference.com/teams/BOS/2024.html") == "first"
    assert client.get("https://www.basketball-reference.com/teams/BOS/2025.html") == "second"
    assert clock.sleeps == [MINIMUM_SCRAPER_DELAY_SECONDS]


@pytest.mark.unit
def test_client_honors_a_delay_slower_than_the_floor_and_the_rpm_gap() -> None:
    clock = FakeClock()
    responses = iter(["first", "second"])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=next(responses))

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = BasketballReferenceClient(
        _settings(scraper_min_delay_seconds=12.0, scraper_max_requests_per_minute=20),
        http_client=http_client,
        sleeper=clock.sleep,
        clock=clock,
    )

    assert client.get("https://www.basketball-reference.com/teams/BOS/2024.html") == "first"
    assert client.get("https://www.basketball-reference.com/teams/BOS/2025.html") == "second"
    assert clock.sleeps == [12.0]


@pytest.mark.unit
def test_client_stops_on_the_first_429_by_default() -> None:
    """AGENTS.md says stop on 429; both acquisition CLIs already pass this explicitly."""
    clock = FakeClock()
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429, headers={"Retry-After": "7"})

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = BasketballReferenceClient(
        _settings(),
        http_client=http_client,
        sleeper=clock.sleep,
        clock=clock,
    )

    with pytest.raises(RateLimitExceededError):
        client.get("https://www.basketball-reference.com/teams/BOS/2024.html")

    assert calls == 1
    assert clock.sleeps == []


@pytest.mark.unit
def test_client_retries_once_after_429() -> None:
    clock = FakeClock()
    responses = iter(
        [
            httpx.Response(429, headers={"Retry-After": "7"}),
            httpx.Response(200, text="<html>ok</html>"),
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return next(responses)

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = BasketballReferenceClient(
        _settings(),
        http_client=http_client,
        sleeper=clock.sleep,
        clock=clock,
        max_429_retries=1,
    )

    assert client.get("https://www.basketball-reference.com/teams/BOS/2024.html") == "<html>ok</html>"
    assert clock.sleeps == [60.0]


@pytest.mark.unit
def test_client_raises_after_repeated_429() -> None:
    clock = FakeClock()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429)

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = BasketballReferenceClient(
        _settings(),
        http_client=http_client,
        sleeper=clock.sleep,
        clock=clock,
        max_429_retries=1,
    )

    with pytest.raises(RateLimitExceededError):
        client.get("https://www.basketball-reference.com/teams/BOS/2024.html")
