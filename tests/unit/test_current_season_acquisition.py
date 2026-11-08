from __future__ import annotations

import json
import re
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from typer.testing import CliRunner

from nba_data.cli.main import app
from nba_data.config.settings import MINIMUM_SCRAPER_DELAY_SECONDS, Settings, get_settings
from nba_data.scraping.cache import CacheFetchMetadata, HtmlCache
from nba_data.scraping.client import (
    BasketballReferenceClient,
    FetchResult,
    RateLimitExceededError,
    RequestBudgetExhaustedError,
)
from nba_data.scraping.current_season_acquisition import (
    PLACEHOLDER_USER_AGENT,
    CurrentSeasonAcquisitionConfigurationError,
    CurrentSeasonAcquisitionStopped,
    build_current_season_dry_run_report,
    refresh_current_season,
    validate_current_season_acquisition_settings,
    validate_settings_within_manifest_policy,
)
from nba_data.scraping.current_season_manifest import (
    CurrentSeasonManifest,
    build_draft_current_season_manifest,
    validate_current_season_manifest,
)
from nba_data.scraping.snapshot_cache import SnapshotCache

BASE = "https://www.basketball-reference.com"
SEASON_URL = f"{BASE}/leagues/NBA_2027_games.html"
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "html"
SEASON_PAGE = (FIXTURES / "league_schedule_2027_trimmed.html").read_text(encoding="utf-8")
TEAMS = [
    "ATL",
    "BOS",
    "BRK",
    "CHO",
    "CHI",
    "CLE",
    "DAL",
    "DEN",
    "DET",
    "GSW",
    "HOU",
    "IND",
    "LAC",
    "LAL",
    "MEM",
    "MIA",
    "MIL",
    "MIN",
    "NOP",
    "NYK",
    "OKC",
    "ORL",
    "PHI",
    "PHO",
    "POR",
    "SAC",
    "SAS",
    "TOR",
    "UTA",
    "WAS",
]
MONTHS = ("october", "november", "december", "january", "february", "march", "april")
TEST_USER_AGENT = "nba-data-tests/0.1 contact:tests@nba-data.invalid"
BOX_SCORE = "<!DOCTYPE html><html><body>box score</body></html>"
TEAM_PAGE = "<!DOCTYPE html><html><body>team page</body></html>"

Game = tuple[date, str, str, tuple[int, int] | None]


def month_url(month: str) -> str:
    return f"{BASE}/leagues/NBA_2027_games-{month}.html"


def team_url(team: str) -> str:
    return f"{BASE}/teams/{team}/2027.html"


def box_url(game_id: str) -> str:
    return f"{BASE}/boxscores/{game_id}.html"


def schedule_page(games: Sequence[Game]) -> str:
    """The cached 2027 season page with its rows replaced, in the page's own row markup."""

    head, _, rest = SEASON_PAGE.partition("<tbody>")
    _, _, tail = rest.partition("</tbody>")
    return f"{head}<tbody>{''.join(_row(game) for game in games)}</tbody>{tail}"


def _row(game: Game) -> str:
    day, visitor, home, score = game
    game_id = f"{day:%Y%m%d}0{home}"
    visitor_pts, home_pts = ("", "") if score is None else (str(score[0]), str(score[1]))
    box = "" if score is None else f'<a href="/boxscores/{game_id}.html">Box Score</a>'
    return (
        f'<tr><th class="left" csk="{game_id}" data-stat="date_game" scope="row">'
        f'<a href="/boxscores/index.fcgi?month={day.month}&amp;day={day.day}&amp;year={day.year}">'
        f"{day:%a, %b} {day.day}, {day.year}</a></th>"
        '<td class="right" data-stat="game_start_time">7:00p</td>'
        f'<td class="left" data-stat="visitor_team_name"><a href="/teams/{visitor}/2027.html">'
        f"{visitor} team</a></td>"
        f'<td class="right" data-stat="visitor_pts">{visitor_pts}</td>'
        f'<td class="left" data-stat="home_team_name"><a href="/teams/{home}/2027.html">'
        f"{home} team</a></td>"
        f'<td class="right" data-stat="home_pts">{home_pts}</td>'
        f'<td class="center" data-stat="box_score_text">{box}</td>'
        '<td class="center iz" data-stat="overtimes"></td>'
        '<td class="right" data-stat="attendance"></td>'
        '<td class="right" data-stat="game_duration"></td>'
        '<td class="left" data-stat="arena_name">Arena</td>'
        '<td class="left iz" data-stat="game_remarks"></td></tr>'
    )


def round_of_games(day: date, *, scored: bool) -> list[Game]:
    return [
        (day, TEAMS[i], TEAMS[i + 1], (100, 101) if scored else None)
        for i in range(0, len(TEAMS), 2)
    ]


def game_ids(games: Sequence[Game]) -> list[str]:
    return [f"{day:%Y%m%d}0{home}" for day, _, home, score in games if score is not None]


class FakeSite:
    """Basketball Reference as of one day: what each URL returns right now."""

    def __init__(self, months: dict[str, list[Game]]) -> None:
        self.pages: dict[str, str] = {SEASON_URL: SEASON_PAGE}
        self.update(months)

    def update(self, months: dict[str, list[Game]]) -> None:
        for month in MONTHS:
            self.pages[month_url(month)] = schedule_page(months.get(month, []))
        for team in TEAMS:
            self.pages[team_url(team)] = TEAM_PAGE

    def get(self, url: str) -> str:
        if url in self.pages:
            return self.pages[url]
        if url.startswith(f"{BASE}/boxscores/"):
            return BOX_SCORE
        msg = f"unexpected URL {url}"
        raise AssertionError(msg)


class FakeClock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


class FakeClient:
    """Counts requests, honours a budget, stamps every fetch with a later time."""

    def __init__(
        self,
        site: FakeSite,
        *,
        rate_limit_on: str | None = None,
        fail_on: str | None = None,
        max_requests: int | None = None,
        start: datetime = datetime(2026, 10, 25, 12, 0, tzinfo=UTC),
    ) -> None:
        self.site = site
        self.rate_limit_on = rate_limit_on
        self.fail_on = fail_on
        self.max_requests = max_requests
        self.clock = FakeClock()
        self.fetched_at = start
        self.calls: list[str] = []
        self._request_count = 0

    @property
    def request_count(self) -> int:
        return self._request_count

    def fetch(self, url: str, *, force_refresh: bool = False) -> FetchResult:
        assert force_refresh is False
        if self.max_requests is not None and self._request_count >= self.max_requests:
            msg = f"planned budget exhausted before {url}"
            raise RequestBudgetExhaustedError(msg)
        self.calls.append(url)
        self._request_count += 1
        self.clock.now += 7.0
        self.fetched_at += timedelta(seconds=7)
        if url == self.rate_limit_on:
            msg = f"planned rate limit for {url}"
            raise RateLimitExceededError(msg, retry_after_seconds=120.0)
        if url == self.fail_on:
            msg = f"planned failure for {url}"
            raise RuntimeError(msg)
        metadata = CacheFetchMetadata(fetched_at=self.fetched_at, http_status=200, final_url=url)
        return FetchResult(html=self.site.get(url), metadata=metadata)


@pytest.fixture(autouse=True)
def clear_settings_cache() -> None:
    get_settings.cache_clear()


def _raw_manifest(*, approved: bool = True, **scope: Any) -> dict[str, Any]:
    raw = build_draft_current_season_manifest(datetime(2026, 11, 7, tzinfo=UTC))
    raw["scope"].update(scope)  # type: ignore[union-attr]
    if approved:
        raw.update(
            status="approved",
            approved_by_owner=True,
            approved_at="2026-11-07T12:00:00+00:00",
            approval_basis="Test fixture approval.",
        )
    return raw


def _manifest(**kwargs: Any) -> CurrentSeasonManifest:
    return validate_current_season_manifest(_raw_manifest(**kwargs), require_approval=False)


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "scraper_user_agent": TEST_USER_AGENT,
        "scraper_max_requests_per_minute": 10,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


class Stores:
    def __init__(self, root: Path) -> None:
        self.snapshots = SnapshotCache(root / "snapshots")
        self.archive = HtmlCache(root / "html")


def _refresh(
    stores: Stores,
    client: FakeClient,
    as_of: date,
    *,
    manifest: CurrentSeasonManifest | None = None,
    max_fetches: int | None = None,
) -> Any:
    return refresh_current_season(
        manifest or _manifest(),
        as_of=as_of,
        snapshots=stores.snapshots,
        archive=stores.archive,
        client=client,
        max_fetches=max_fetches,
        clock=client.clock,
    )


OCTOBER_PLAYED = round_of_games(date(2026, 10, 21), scored=True)
OCTOBER_LATER = round_of_games(date(2026, 10, 27), scored=False)
FIRST_DAY = {"october": OCTOBER_PLAYED + OCTOBER_LATER}


@pytest.mark.unit
def test_a_first_run_fetches_the_season_every_month_30_team_pages_and_the_box_scores(
    tmp_path: Path,
) -> None:
    stores = Stores(tmp_path)
    client = FakeClient(FakeSite(FIRST_DAY))

    report = _refresh(stores, client, date(2026, 10, 25))

    assert report.completed
    assert report.planned == {"season": 1, "month": 7, "team": 30, "box_score": 15}
    expected = (
        [SEASON_URL]
        + [month_url(month) for month in MONTHS]
        + [team_url(team) for team in sorted(TEAMS)]
        + [box_url(game_id) for game_id in game_ids(OCTOBER_PLAYED)]
    )
    assert client.calls == expected
    assert report.live_request_count == len(expected) == 53
    assert [entry.phase for entry in report.entries] == (
        ["season"] + ["month"] * 7 + ["team"] * 30 + ["box_score"] * 15
    )
    assert stores.snapshots.latest(SEASON_URL) is not None
    assert stores.snapshots.latest(team_url("BOS")) is not None
    assert all(stores.archive.exists(box_url(game_id)) for game_id in game_ids(OCTOBER_PLAYED))
    # Schedule and team pages go to snapshots only; box scores to the archive only.
    assert not stores.archive.exists(SEASON_URL)
    assert not stores.archive.exists(team_url("BOS"))
    assert all(
        Path(entry.path).is_relative_to(tmp_path / "snapshots") for entry in report.entries[:38]
    )
    assert all(Path(entry.path).is_relative_to(tmp_path / "html") for entry in report.entries[38:])


@pytest.mark.unit
def test_a_later_run_fetches_only_new_months_and_new_box_scores_and_no_team_page(
    tmp_path: Path,
) -> None:
    stores = Stores(tmp_path)
    site = FakeSite(FIRST_DAY)
    _refresh(stores, FakeClient(site), date(2026, 10, 25))

    november = round_of_games(date(2026, 11, 1), scored=True)[:3] + round_of_games(
        date(2026, 11, 8), scored=False
    )
    october_settled = OCTOBER_PLAYED + round_of_games(date(2026, 10, 27), scored=True)
    site.update({"october": october_settled, "november": november})
    client = FakeClient(site, start=datetime(2026, 11, 2, 12, 0, tzinfo=UTC))

    report = _refresh(stores, client, date(2026, 11, 2))

    assert report.completed
    assert report.planned == {"season": 1, "month": 3, "team": 0, "box_score": 18}
    new_box_scores = game_ids(round_of_games(date(2026, 10, 27), scored=True)) + game_ids(november)
    assert client.calls == (
        [SEASON_URL, month_url("october"), month_url("november"), month_url("december")]
        + [box_url(game_id) for game_id in new_box_scores]
    )
    assert len(stores.snapshots.history(month_url("october"))) == 2
    assert len(stores.snapshots.history(month_url("april"))) == 1
    assert len(stores.snapshots.history(team_url("BOS"))) == 1


@pytest.mark.unit
def test_a_late_score_is_picked_up_from_an_earlier_month(tmp_path: Path) -> None:
    stores = Stores(tmp_path)
    late = (date(2026, 10, 30), "BOS", "NYK", None)
    site = FakeSite({"october": [*OCTOBER_PLAYED, late]})
    _refresh(stores, FakeClient(site), date(2026, 10, 31))

    site.update({"october": [*OCTOBER_PLAYED, (late[0], late[1], late[2], (99, 98))]})
    client = FakeClient(site, start=datetime(2026, 12, 10, tzinfo=UTC))
    report = _refresh(stores, client, date(2026, 12, 10))

    assert month_url("october") in client.calls
    assert month_url("november") not in client.calls
    assert client.calls[-1] == box_url("202610300NYK")
    assert report.planned["box_score"] == 1


@pytest.mark.unit
def test_a_postponed_row_is_refetched_but_never_fetches_a_box_score(tmp_path: Path) -> None:
    stores = Stores(tmp_path)
    postponed = (date(2026, 10, 22), "LAL", "MIA", None)
    site = FakeSite({"october": [*OCTOBER_PLAYED, postponed]})
    _refresh(stores, FakeClient(site), date(2026, 10, 25))

    client = FakeClient(site, start=datetime(2026, 12, 10, tzinfo=UTC))
    report = _refresh(stores, client, date(2026, 12, 10))

    assert report.completed
    assert month_url("october") in client.calls
    assert box_url("202610220MIA") not in client.calls
    assert report.planned["box_score"] == 0


@pytest.mark.unit
def test_a_429_mid_run_stops_with_retry_after_and_a_rerun_resumes(tmp_path: Path) -> None:
    stores = Stores(tmp_path)
    site = FakeSite(FIRST_DAY)
    client = FakeClient(site, rate_limit_on=team_url("CHI"))

    with pytest.raises(CurrentSeasonAcquisitionStopped) as stopped:
        _refresh(stores, client, date(2026, 10, 25))

    report = stopped.value.report
    assert report.stopped_reason == "rate_limited"
    assert report.stopped_at_phase == "team"
    assert report.stopped_at_url == team_url("CHI")
    assert report.retry_after_seconds == 120.0
    assert report.rate_limited == 1
    assert report.planned["box_score"] is None
    assert client.calls[-1] == team_url("CHI")
    assert not any("/boxscores/" in url for url in client.calls)
    assert stores.snapshots.latest(team_url("CHI")) is None

    rerun = FakeClient(site, start=datetime(2026, 10, 25, 14, 0, tzinfo=UTC))
    resumed = _refresh(stores, rerun, date(2026, 10, 25))

    assert resumed.completed
    # ATL, BOS and BRK were snapshotted before the 429 at CHI.
    assert resumed.planned == {"season": 1, "month": 2, "team": 27, "box_score": 15}
    assert team_url("ATL") not in rerun.calls
    assert team_url("CHI") in rerun.calls


@pytest.mark.unit
def test_any_failure_stops_the_run_with_a_partial_report(tmp_path: Path) -> None:
    stores = Stores(tmp_path)
    client = FakeClient(FakeSite(FIRST_DAY), fail_on=month_url("november"))

    with pytest.raises(CurrentSeasonAcquisitionStopped) as stopped:
        _refresh(stores, client, date(2026, 10, 25))

    report = stopped.value.report
    assert report.stopped_reason == "failed"
    assert report.stopped_at_phase == "month"
    assert report.failures == 1
    assert "planned failure" in (report.error_details or "")
    assert report.planned["team"] is None


@pytest.mark.unit
def test_bad_month_response_does_not_poison_snapshots_and_a_rerun_recovers(tmp_path: Path) -> None:
    stores = Stores(tmp_path)
    site = FakeSite(FIRST_DAY)
    _refresh(stores, FakeClient(site), date(2026, 10, 25))
    previous = stores.snapshots.latest(month_url("october"))
    site.pages[month_url("october")] = "<html><body>temporarily unavailable</body></html>"

    with pytest.raises(CurrentSeasonAcquisitionStopped) as stopped:
        _refresh(
            stores,
            FakeClient(site, start=datetime(2026, 10, 26, tzinfo=UTC)),
            date(2026, 10, 26),
        )

    assert stopped.value.report.stopped_reason == "failed"
    assert stopped.value.report.stopped_at_url == month_url("october")
    assert stores.snapshots.latest(month_url("october")) == previous
    site.update(FIRST_DAY)
    resumed = _refresh(
        stores,
        FakeClient(site, start=datetime(2026, 10, 27, tzinfo=UTC)),
        date(2026, 10, 27),
    )
    assert resumed.completed


@pytest.mark.unit
def test_wrong_season_schedule_cannot_authorize_box_score_requests(tmp_path: Path) -> None:
    stores = Stores(tmp_path)
    site = FakeSite(FIRST_DAY)
    site.pages[month_url("october")] = schedule_page(
        [(date(2025, 10, 21), "BOS", "NYK", (100, 99))]
    )
    client = FakeClient(site)

    with pytest.raises(CurrentSeasonAcquisitionStopped) as stopped:
        _refresh(stores, client, date(2026, 10, 25))

    assert "outside the current season" in (stopped.value.report.error_details or "")
    assert stores.snapshots.latest(month_url("october")) is None
    assert not any("/boxscores/" in url for url in client.calls)


@pytest.mark.unit
def test_a_ceiling_exceeded_stops_before_any_box_score(tmp_path: Path) -> None:
    stores = Stores(tmp_path)
    client = FakeClient(FakeSite(FIRST_DAY))

    with pytest.raises(CurrentSeasonAcquisitionStopped) as stopped:
        _refresh(stores, client, date(2026, 10, 25), manifest=_manifest(max_box_scores_per_run=14))

    report = stopped.value.report
    assert report.stopped_reason == "plan_refused"
    assert report.stopped_at_phase == "box_score"
    assert "15 box scores, above the manifest's ceiling of 14" in (report.error_details or "")
    assert not any("/boxscores/" in url for url in client.calls)


@pytest.mark.unit
def test_max_fetches_stops_cleanly_and_counts_live_requests_only(tmp_path: Path) -> None:
    stores = Stores(tmp_path)
    site = FakeSite(FIRST_DAY)
    _refresh(stores, FakeClient(site), date(2026, 10, 25), max_fetches=10)
    for game_id in game_ids(OCTOBER_PLAYED)[:5]:
        stores.archive.set(box_url(game_id), BOX_SCORE)

    client = FakeClient(site, start=datetime(2026, 10, 26, tzinfo=UTC))
    report = _refresh(stores, client, date(2026, 10, 25), max_fetches=40)

    assert report.stopped_reason == "max_fetches"
    assert report.completed is False
    assert report.live_request_count == 40 == len(client.calls)
    # season + 2 months + 28 team pages left from the first batch + 9 box scores
    assert report.planned == {"season": 1, "month": 2, "team": 28, "box_score": 10}
    assert report.cache_hits == 0


@pytest.mark.unit
def test_only_an_approved_manifest_runs_and_as_of_must_be_in_season(tmp_path: Path) -> None:
    stores = Stores(tmp_path)
    client = FakeClient(FakeSite(FIRST_DAY))

    with pytest.raises(CurrentSeasonAcquisitionConfigurationError, match="approved"):
        _refresh(stores, client, date(2026, 10, 25), manifest=_manifest(approved=False))
    with pytest.raises(CurrentSeasonAcquisitionConfigurationError, match="outside the 2027"):
        _refresh(stores, client, date(2027, 11, 1))
    with pytest.raises(CurrentSeasonAcquisitionConfigurationError, match="at least 1"):
        _refresh(stores, client, date(2026, 10, 25), max_fetches=0)
    assert client.calls == []


@pytest.mark.unit
def test_the_real_client_spaces_requests_and_reports_retry_after(tmp_path: Path) -> None:
    site = FakeSite(FIRST_DAY)
    now = [1000.0]
    sleeps: list[float] = []
    sent_at: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent_at.append(now[0])
        url = str(request.url)
        if url == team_url("ATL"):
            return httpx.Response(429, headers={"Retry-After": "300"}, text="slow down")
        return httpx.Response(200, text=site.get(url))

    def sleeper(seconds: float) -> None:
        sleeps.append(seconds)
        now[0] += seconds

    stamps = iter(datetime(2026, 10, 25, tzinfo=UTC) + timedelta(seconds=i) for i in range(100))
    client = BasketballReferenceClient(
        _settings(),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleeper=sleeper,
        clock=lambda: now[0],
        now=lambda: next(stamps),
        max_429_retries=0,
    )
    stores = Stores(tmp_path)

    with pytest.raises(CurrentSeasonAcquisitionStopped) as stopped:
        refresh_current_season(
            _manifest(),
            as_of=date(2026, 10, 25),
            snapshots=stores.snapshots,
            archive=stores.archive,
            client=client,
        )

    assert len(sent_at) == 9  # season page, 7 months, the 429
    gaps = [later - earlier for earlier, later in zip(sent_at, sent_at[1:], strict=False)]
    assert all(gap >= MINIMUM_SCRAPER_DELAY_SECONDS for gap in gaps)
    assert stopped.value.report.retry_after_seconds == 300.0


@pytest.mark.unit
def test_the_dry_run_plans_from_the_latest_snapshots_offline(tmp_path: Path) -> None:
    stores = Stores(tmp_path)
    settings = _settings()
    draft = _manifest(approved=False)

    empty = build_current_season_dry_run_report(
        draft,
        as_of=date(2026, 10, 25),
        snapshots=stores.snapshots,
        archive=stores.archive,
        settings=settings,
    ).to_dict()
    assert empty["status"] == "draft"
    assert empty["planned"] == {"season": 1, "month": None, "team": None, "box_score": 0}
    assert empty["estimated_fetch_count"] == 1

    site = FakeSite(FIRST_DAY)
    _refresh(stores, FakeClient(site), date(2026, 10, 25))
    stores.snapshots.write(
        month_url("october"),
        schedule_page(OCTOBER_PLAYED + round_of_games(date(2026, 10, 27), scored=True)),
        CacheFetchMetadata(
            fetched_at=datetime(2026, 11, 1, tzinfo=UTC), http_status=200, final_url=SEASON_URL
        ),
    )
    report = build_current_season_dry_run_report(
        draft,
        as_of=date(2026, 11, 2),
        snapshots=stores.snapshots,
        archive=stores.archive,
        settings=settings,
    ).to_dict()
    assert report["planned"] == {"season": 1, "month": 2, "team": 0, "box_score": 15}
    assert report["estimated_fetch_count"] == 18
    assert report["estimated_minimum_seconds"] == 17 * 6.0


@pytest.mark.unit
@pytest.mark.parametrize("user_agent", [PLACEHOLDER_USER_AGENT, "bot contact:me@example.com"])
def test_the_placeholder_user_agent_is_refused(user_agent: str) -> None:
    with pytest.raises(CurrentSeasonAcquisitionConfigurationError, match="placeholder"):
        validate_current_season_acquisition_settings(_settings(scraper_user_agent=user_agent))


@pytest.mark.unit
def test_settings_faster_than_allowed_or_approved_are_refused() -> None:
    with pytest.raises(CurrentSeasonAcquisitionConfigurationError, match="at most 10"):
        validate_current_season_acquisition_settings(_settings(scraper_max_requests_per_minute=12))
    manifest = validate_current_season_manifest(
        {
            **_raw_manifest(),
            "acquisition_policy": {
                **_raw_manifest()["acquisition_policy"],
                "requests_per_minute": 6,
            },
        },
        require_approval=True,
    )
    with pytest.raises(CurrentSeasonAcquisitionConfigurationError, match="the manifest approves"):
        validate_settings_within_manifest_policy(_settings(), manifest)


# --- CLI -------------------------------------------------------------------------------------


def _forbid_client_creation(monkeypatch: pytest.MonkeyPatch) -> list[object]:
    created: list[object] = []

    class ForbiddenClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            created.append(self)

    monkeypatch.setattr("nba_data.cli.main.BasketballReferenceClient", ForbiddenClient)
    return created


def _cli_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SCRAPER_CACHE_DIR", str(tmp_path / "html"))
    monkeypatch.setenv("SCRAPER_SNAPSHOT_DIR", str(tmp_path / "snapshots"))
    monkeypatch.setenv("SCRAPER_MAX_REQUESTS_PER_MINUTE", "10")
    monkeypatch.setenv("SCRAPER_USER_AGENT", TEST_USER_AGENT)


def _write_manifest(tmp_path: Path, raw: dict[str, Any] | None = None) -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(raw or _raw_manifest()), encoding="utf-8")
    return path


def _acquire_args(path: Path, *extra: str) -> list[str]:
    return [
        "acquisition",
        "acquire-current-season",
        str(path),
        "--as-of",
        "2026-10-25",
        "--owner-approved",
        "--execute-approved-manifest",
        *extra,
    ]


def _flat(output: str) -> str:
    return " ".join(re.sub(r"[─-╿|]", " ", output).split())


@pytest.mark.unit
@pytest.mark.parametrize(
    "flags",
    [[], ["--owner-approved"], ["--execute-approved-manifest"]],
)
def test_cli_refuses_without_both_flags_before_reading_the_manifest(
    flags: list[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = _forbid_client_creation(monkeypatch)
    read: list[object] = []
    monkeypatch.setattr(
        "nba_data.cli.main.load_current_season_manifest",
        lambda path, **kwargs: read.append(path),
    )

    result = CliRunner().invoke(
        app,
        [
            "acquisition",
            "acquire-current-season",
            str(tmp_path / "absent.json"),
            "--as-of",
            "2026-10-25",
            *flags,
        ],
    )

    assert result.exit_code == 1
    assert "Refusing acquisition without --owner-approved and --execute-approved-manifest" in (
        result.output
    )
    assert read == []
    assert created == []


@pytest.mark.unit
@pytest.mark.parametrize(
    ("raw", "message"),
    [
        (_raw_manifest(approved=False), "status must be 'approved'"),
        (
            {**_raw_manifest(), "scope": {**_raw_manifest()["scope"], "season_end_year": 2026}},
            "current season 2027",
        ),
        (_raw_manifest(max_box_scores_per_run=151), "between 1 and 150"),
        (_raw_manifest(max_team_pages_per_run=31), "between 1 and 30"),
        (_raw_manifest(max_schedule_pages_per_run=21), "between 1 and 20"),
    ],
    ids=["draft", "other-season", "box-ceiling", "team-ceiling", "schedule-ceiling"],
)
def test_cli_refuses_unsafe_manifests_before_creating_a_client(
    raw: dict[str, Any],
    message: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _cli_env(monkeypatch, tmp_path)
    created = _forbid_client_creation(monkeypatch)

    result = CliRunner().invoke(app, _acquire_args(_write_manifest(tmp_path, raw)))

    assert result.exit_code == 2
    assert message in _flat(result.output)
    assert created == []


@pytest.mark.unit
def test_cli_refuses_the_placeholder_user_agent_before_creating_a_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _cli_env(monkeypatch, tmp_path)
    monkeypatch.setenv("SCRAPER_USER_AGENT", PLACEHOLDER_USER_AGENT)
    created = _forbid_client_creation(monkeypatch)

    result = CliRunner().invoke(app, _acquire_args(_write_manifest(tmp_path)))

    assert result.exit_code == 2
    assert "SCRAPER_USER_AGENT is the placeholder" in _flat(result.output)
    assert created == []


@pytest.mark.unit
@pytest.mark.parametrize("as_of", ["2026-1-5", "tomorrow", "2026-02-30"])
def test_cli_refuses_an_as_of_that_is_not_a_date(
    as_of: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _cli_env(monkeypatch, tmp_path)
    created = _forbid_client_creation(monkeypatch)
    args = _acquire_args(_write_manifest(tmp_path))
    args[args.index("2026-10-25")] = as_of

    result = CliRunner().invoke(app, args)

    assert result.exit_code == 2
    assert "YYYY-MM-DD" in _flat(result.output)
    assert created == []


def _cli_client_class(instances: list[FakeClient], site: FakeSite, **kwargs: Any) -> type:
    class CliClient(FakeClient):
        def __init__(self, settings: Settings, **options: Any) -> None:
            assert options["max_429_retries"] == 0
            assert options["follow_redirects"] is False
            super().__init__(site, max_requests=options["max_requests"], **kwargs)
            instances.append(self)

        def __enter__(self) -> CliClient:
            return self

        def __exit__(self, *exc_info: object) -> None:
            return None

    return CliClient


@pytest.mark.unit
def test_cli_runs_one_refresh_and_writes_the_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _cli_env(monkeypatch, tmp_path)
    instances: list[FakeClient] = []
    monkeypatch.setattr(
        "nba_data.cli.main.BasketballReferenceClient",
        _cli_client_class(instances, FakeSite(FIRST_DAY)),
    )
    output = tmp_path / "reports" / "refresh.json"

    result = CliRunner().invoke(
        app,
        _acquire_args(_write_manifest(tmp_path), "--max-fetches", "60", "--output", str(output)),
    )

    assert result.exit_code == 0, result.output
    assert instances[0].max_requests == 60
    written = json.loads(output.read_text(encoding="utf-8"))
    assert written["completed"] is True
    assert written["planned"] == {"season": 1, "month": 7, "team": 30, "box_score": 15}
    assert {entry["phase"] for entry in written["entries"]} == {
        "season",
        "month",
        "team",
        "box_score",
    }


@pytest.mark.unit
def test_cli_writes_the_partial_report_and_exits_1_on_a_429(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _cli_env(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "nba_data.cli.main.BasketballReferenceClient",
        _cli_client_class([], FakeSite(FIRST_DAY), rate_limit_on=month_url("march")),
    )
    output = tmp_path / "reports" / "partial.json"

    result = CliRunner().invoke(
        app, _acquire_args(_write_manifest(tmp_path), "--output", str(output))
    )

    assert result.exit_code == 1
    written = json.loads(output.read_text(encoding="utf-8"))
    assert written["stopped_reason"] == "rate_limited"
    assert written["stopped_at_phase"] == "month"
    assert written["retry_after_seconds"] == 120.0


@pytest.mark.unit
def test_cli_dry_run_reads_a_draft_and_never_creates_a_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _cli_env(monkeypatch, tmp_path)
    created = _forbid_client_creation(monkeypatch)

    result = CliRunner().invoke(
        app,
        [
            "acquisition",
            "dry-run-current-season",
            str(_write_manifest(tmp_path, _raw_manifest(approved=False))),
            "--as-of",
            "2026-10-25",
        ],
    )

    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert report["status"] == "draft"
    assert report["planned"] == {"season": 1, "month": None, "team": None, "box_score": 0}
    assert created == []


@pytest.mark.unit
def test_cli_dry_run_reports_a_ceiling_exceeded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _cli_env(monkeypatch, tmp_path)
    stores = Stores(tmp_path)
    _refresh(stores, FakeClient(FakeSite(FIRST_DAY)), date(2026, 10, 25))

    result = CliRunner().invoke(
        app,
        [
            "acquisition",
            "dry-run-current-season",
            str(_write_manifest(tmp_path, _raw_manifest(approved=False))),
            "--as-of",
            "2026-10-25",
        ],
    )
    assert result.exit_code == 0, result.output

    stores.snapshots.write(
        month_url("october"),
        schedule_page(OCTOBER_PLAYED + round_of_games(date(2026, 10, 27), scored=True)),
        CacheFetchMetadata(
            fetched_at=datetime(2026, 11, 1, tzinfo=UTC), http_status=200, final_url=SEASON_URL
        ),
    )
    small = _raw_manifest(approved=False, max_box_scores_per_run=10)
    result = CliRunner().invoke(
        app,
        [
            "acquisition",
            "dry-run-current-season",
            str(_write_manifest(tmp_path, small)),
            "--as-of",
            "2026-11-02",
        ],
    )

    assert result.exit_code == 2
    assert "15 box scores, above the manifest's ceiling of 10" in _flat(result.output)
