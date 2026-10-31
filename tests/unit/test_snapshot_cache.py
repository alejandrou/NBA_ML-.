import gzip
import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

import nba_data.scraping.snapshot_cache as snapshot_cache
from nba_data.scraping.cache import CacheFetchMetadata, CacheMetadataError, HtmlCache
from nba_data.scraping.cache_inventory import build_cached_html_inventory
from nba_data.scraping.cache_writer import CacheWriteError
from nba_data.scraping.snapshot_cache import (
    CURRENT_SEASON_END_YEAR,
    SnapshotCache,
    SnapshotCacheError,
    is_mutable_page,
)

OCTOBER_URL = "https://www.basketball-reference.com/leagues/NBA_2027_games-october.html"
SEASON_URL = "https://www.basketball-reference.com/leagues/NBA_2027_games.html"
BOS_2027_URL = "https://www.basketball-reference.com/teams/BOS/2027.html"
FIRST_FETCH = datetime(2026, 10, 20, 12, 0, 0, 123456, tzinfo=UTC)
SECOND_FETCH = datetime(2026, 11, 1, 12, 0, 0, tzinfo=UTC)


def _html(label: str) -> str:
    return f"<!DOCTYPE html><html><body>{label}</body></html>"


def _metadata(fetched_at: datetime = FIRST_FETCH, url: str = OCTOBER_URL) -> CacheFetchMetadata:
    return CacheFetchMetadata(fetched_at=fetched_at, http_status=200, final_url=url)


def _files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.is_file())


@pytest.mark.unit
def test_current_season_is_2027() -> None:
    assert CURRENT_SEASON_END_YEAR == 2027


@pytest.mark.unit
@pytest.mark.parametrize(
    "url",
    [
        SEASON_URL,
        OCTOBER_URL,
        "https://basketball-reference.com/leagues/NBA_2027_games-april.html",
        BOS_2027_URL,
    ],
)
def test_current_season_schedule_and_team_pages_are_mutable(url: str) -> None:
    assert is_mutable_page(url)


@pytest.mark.unit
@pytest.mark.parametrize(
    "url",
    [
        "https://www.basketball-reference.com/boxscores/202610210BOS.html",
        "https://www.basketball-reference.com/boxscores/pbp/202610210BOS.html",
        "https://www.basketball-reference.com/teams/BOS/2026.html",
        "https://www.basketball-reference.com/leagues/NBA_2026_games-october.html",
        "https://www.basketball-reference.com/teams/TOT/2027.html",
        "https://www.basketball-reference.com/teams/BOS/2027_games.html",
        "https://www.basketball-reference.com/teams/BOS/2027.html?x=1",
        "http://www.basketball-reference.com/teams/BOS/2027.html",
        "https://example.com/teams/BOS/2027.html",
    ],
)
def test_other_pages_are_immutable(url: str) -> None:
    assert not is_mutable_page(url)


@pytest.mark.unit
def test_two_writes_keep_both_and_latest_is_the_second(tmp_path) -> None:
    cache = SnapshotCache(tmp_path)

    first = cache.write(OCTOBER_URL, _html("first"), _metadata(FIRST_FETCH))
    second = cache.write(OCTOBER_URL, _html("second"), _metadata(SECOND_FETCH))

    assert first != second
    assert first.exists() and second.exists()
    assert first.name == "20261020T120000123456Z.html.gz"
    assert first.parent == cache.directory_for_url(OCTOBER_URL)
    latest = cache.latest(OCTOBER_URL)
    assert latest is not None
    assert latest.body == _html("second")
    assert latest.metadata == _metadata(SECOND_FETCH)
    assert latest.path == second


@pytest.mark.unit
def test_history_is_oldest_first_whatever_the_write_order(tmp_path) -> None:
    cache = SnapshotCache(tmp_path)
    fetches = [SECOND_FETCH, FIRST_FETCH, SECOND_FETCH + timedelta(days=1)]
    for index, fetched_at in enumerate(fetches):
        cache.write(OCTOBER_URL, _html(str(index)), _metadata(fetched_at))

    history = cache.history(OCTOBER_URL)

    assert [snapshot.metadata.fetched_at for snapshot in history] == sorted(fetches)
    assert [snapshot.body for snapshot in history] == [_html("1"), _html("0"), _html("2")]


@pytest.mark.unit
def test_a_page_never_snapshotted_has_no_latest(tmp_path) -> None:
    cache = SnapshotCache(tmp_path)

    assert cache.latest(SEASON_URL) is None
    assert cache.history(SEASON_URL) == ()


@pytest.mark.unit
def test_a_non_utc_fetch_time_is_stamped_in_utc(tmp_path) -> None:
    cache = SnapshotCache(tmp_path)
    eastern = FIRST_FETCH.astimezone(timezone(timedelta(hours=-4)))

    path = cache.write(OCTOBER_URL, _html("x"), _metadata(eastern))

    assert path.name == "20261020T120000123456Z.html.gz"
    latest = cache.latest(OCTOBER_URL)
    assert latest is not None and latest.metadata.fetched_at == FIRST_FETCH


@pytest.mark.unit
@pytest.mark.parametrize(
    "url",
    [
        "https://www.basketball-reference.com/boxscores/202610210BOS.html",
        "https://www.basketball-reference.com/teams/BOS/2026.html",
    ],
)
def test_write_refuses_an_immutable_page(tmp_path, url: str) -> None:
    cache = SnapshotCache(tmp_path)

    with pytest.raises(CacheWriteError, match="not mutable"):
        cache.write(url, _html("x"), _metadata(url=url))

    assert _files(tmp_path) == []


@pytest.mark.unit
def test_write_refuses_missing_metadata(tmp_path) -> None:
    cache = SnapshotCache(tmp_path)

    with pytest.raises(CacheWriteError, match="metadata"):
        cache.write(OCTOBER_URL, _html("x"), None)  # type: ignore[arg-type]

    assert _files(tmp_path) == []


@pytest.mark.unit
def test_write_refuses_a_naive_fetch_time(tmp_path) -> None:
    cache = SnapshotCache(tmp_path)
    metadata = _metadata()
    # CacheFetchMetadata refuses a naive time itself; force one past it.
    object.__setattr__(metadata, "fetched_at", FIRST_FETCH.replace(tzinfo=None))

    with pytest.raises(ValueError, match="timezone-aware"):
        cache.write(OCTOBER_URL, _html("x"), metadata)

    assert _files(tmp_path) == []


@pytest.mark.unit
@pytest.mark.parametrize("html", ["", "   ", '{"not": "html"}'])
def test_write_refuses_non_html(tmp_path, html: str) -> None:
    cache = SnapshotCache(tmp_path)

    with pytest.raises(ValueError):
        cache.write(OCTOBER_URL, html, _metadata())

    assert _files(tmp_path) == []


@pytest.mark.unit
def test_write_refuses_a_second_snapshot_with_the_same_timestamp(tmp_path) -> None:
    cache = SnapshotCache(tmp_path)
    path = cache.write(OCTOBER_URL, _html("first"), _metadata())

    with pytest.raises(CacheWriteError, match="Refusing to overwrite"):
        cache.write(OCTOBER_URL, _html("second"), _metadata())

    with gzip.open(path, "rt", encoding="utf-8") as file:
        assert file.read() == _html("first")


@pytest.mark.unit
def test_the_publish_primitive_refuses_a_target_created_after_the_check(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = SnapshotCache(tmp_path)
    original = snapshot_cache._publish

    def racing_publish(temp_path: Path, final_path: Path, what: str) -> None:
        if what == "snapshot metadata file":
            final_path.write_text("another writer", encoding="utf-8")
        original(temp_path, final_path, what)

    monkeypatch.setattr(snapshot_cache, "_publish", racing_publish)

    with pytest.raises(CacheWriteError, match="Refusing to overwrite"):
        cache.write(OCTOBER_URL, _html("x"), _metadata())

    sidecars = _files(tmp_path)
    assert len(sidecars) == 1
    assert sidecars[0].read_text(encoding="utf-8") == "another writer"


@pytest.mark.unit
def test_a_crash_between_sidecar_and_body_publishes_nothing(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = SnapshotCache(tmp_path)
    original = snapshot_cache._publish

    def failing_publish(temp_path: Path, final_path: Path, what: str) -> None:
        if what == "snapshot file":
            raise OSError("disk full")
        original(temp_path, final_path, what)

    monkeypatch.setattr(snapshot_cache, "_publish", failing_publish)

    with pytest.raises(OSError, match="disk full"):
        cache.write(OCTOBER_URL, _html("x"), _metadata())

    assert _files(tmp_path) == []
    assert cache.latest(OCTOBER_URL) is None


@pytest.mark.unit
def test_a_body_without_a_sidecar_raises(tmp_path) -> None:
    cache = SnapshotCache(tmp_path)
    path = cache.write(OCTOBER_URL, _html("x"), _metadata())
    path.with_name(path.name + ".meta.json").unlink()

    with pytest.raises(SnapshotCacheError, match="no metadata sidecar"):
        cache.latest(OCTOBER_URL)


@pytest.mark.unit
def test_a_sidecar_without_a_body_is_not_a_snapshot(tmp_path) -> None:
    cache = SnapshotCache(tmp_path)
    cache.write(OCTOBER_URL, _html("first"), _metadata(FIRST_FETCH))
    second = cache.write(OCTOBER_URL, _html("second"), _metadata(SECOND_FETCH))
    second.unlink()

    latest = cache.latest(OCTOBER_URL)

    assert latest is not None and latest.body == _html("first")


@pytest.mark.unit
def test_a_sidecar_dated_differently_from_its_name_raises(tmp_path) -> None:
    cache = SnapshotCache(tmp_path)
    path = cache.write(OCTOBER_URL, _html("x"), _metadata())
    sidecar = path.with_name(path.name + ".meta.json")
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    payload["fetched_at"] = SECOND_FETCH.isoformat()
    sidecar.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(SnapshotCacheError, match="sidecar says"):
        cache.latest(OCTOBER_URL)


@pytest.mark.unit
def test_an_unreadable_sidecar_raises(tmp_path) -> None:
    cache = SnapshotCache(tmp_path)
    path = cache.write(OCTOBER_URL, _html("x"), _metadata())
    path.with_name(path.name + ".meta.json").write_text("{not json", encoding="utf-8")

    with pytest.raises(CacheMetadataError):
        cache.latest(OCTOBER_URL)


@pytest.mark.unit
def test_a_body_whose_name_is_not_a_timestamp_raises(tmp_path) -> None:
    cache = SnapshotCache(tmp_path)
    cache.write(OCTOBER_URL, _html("x"), _metadata())
    stray = cache.directory_for_url(OCTOBER_URL) / "latest.html.gz"
    with gzip.open(stray, "wt", encoding="utf-8") as file:
        file.write(_html("stray"))

    with pytest.raises(SnapshotCacheError, match="not a fetch timestamp"):
        cache.latest(OCTOBER_URL)


@pytest.mark.unit
def test_snapshots_never_appear_in_the_archive_inventory(tmp_path) -> None:
    archive = HtmlCache(tmp_path / "raw" / "html")
    archive.set(
        "https://www.basketball-reference.com/teams/BOS/2024.html",
        _html("archived"),
        metadata=_metadata(url="https://www.basketball-reference.com/teams/BOS/2024.html"),
    )
    before = build_cached_html_inventory(cache=archive)
    snapshots = SnapshotCache(tmp_path / "raw" / "snapshots")

    snapshots.write(BOS_2027_URL, _html("bos"), _metadata(url=BOS_2027_URL))
    snapshots.write(OCTOBER_URL, _html("october"), _metadata())

    after = build_cached_html_inventory(cache=archive)
    assert after == before
    assert after.total_discovered_files == 1
    assert all(snapshots.root_dir not in Path(entry.cache_path).parents for entry in after.entries)


@pytest.mark.unit
def test_the_archive_copy_is_untouched_and_ignored(tmp_path) -> None:
    archive = HtmlCache(tmp_path / "raw" / "html")
    archive_path = archive.set(
        OCTOBER_URL, _html("pilot october"), metadata=_metadata(FIRST_FETCH - timedelta(days=40))
    )
    archive_files_before = {path: path.read_bytes() for path in _files(archive.root_dir)}
    snapshots = SnapshotCache(tmp_path / "raw" / "snapshots")

    snapshots.write(OCTOBER_URL, _html("fresh october"), _metadata())

    assert {path: path.read_bytes() for path in _files(archive.root_dir)} == archive_files_before
    assert archive.get(OCTOBER_URL) == _html("pilot october")
    latest = snapshots.latest(OCTOBER_URL)
    assert latest is not None and latest.body == _html("fresh october")
    assert archive.root_dir not in latest.path.parents
    assert latest.path.parent.name == archive_path.name.removesuffix(".html.gz")


def _page_directory(cache: SnapshotCache, url: str) -> Path:
    """Where a page's snapshots go, computed without the root-escape check."""

    path = cache._names.path_for_url(url)
    return path.with_name(path.name.removesuffix(".html.gz"))


def _link_directory(link: Path, target: Path) -> None:
    """Plant a directory link: a junction on Windows, a symlink elsewhere."""

    link.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        import _winapi

        _winapi.CreateJunction(str(target), str(link))
    else:
        os.symlink(target, link, target_is_directory=True)


@pytest.mark.unit
@pytest.mark.parametrize("level", ["page directory", "host directory"])
def test_write_refuses_a_link_that_leaves_the_root(tmp_path, level: str) -> None:
    cache = SnapshotCache(tmp_path / "snapshots")
    outside = tmp_path / "outside"
    outside.mkdir()
    page_directory = _page_directory(cache, OCTOBER_URL)
    _link_directory(page_directory if level == "page directory" else page_directory.parent, outside)

    with pytest.raises(SnapshotCacheError, match="escaped root"):
        cache.write(OCTOBER_URL, _html("x"), _metadata())

    assert _files(outside) == []


@pytest.mark.unit
def test_reads_refuse_a_link_that_leaves_the_root(tmp_path) -> None:
    outside_cache = SnapshotCache(tmp_path / "outside")
    outside_cache.write(OCTOBER_URL, _html("planted"), _metadata())
    cache = SnapshotCache(tmp_path / "snapshots")
    _link_directory(
        _page_directory(cache, OCTOBER_URL), outside_cache.directory_for_url(OCTOBER_URL)
    )

    with pytest.raises(SnapshotCacheError, match="escaped root"):
        cache.latest(OCTOBER_URL)
    with pytest.raises(SnapshotCacheError, match="escaped root"):
        cache.history(OCTOBER_URL)


@pytest.mark.unit
def test_latest_reads_only_the_newest_body(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache = SnapshotCache(tmp_path)
    oldest = cache.write(OCTOBER_URL, _html("first"), _metadata(FIRST_FETCH))
    cache.write(OCTOBER_URL, _html("second"), _metadata(SECOND_FETCH))
    oldest.write_bytes(oldest.read_bytes()[:10])
    reads: list[Path] = []
    original = snapshot_cache._read_body

    def counting_read(path: Path, metadata: CacheFetchMetadata) -> snapshot_cache.Snapshot:
        reads.append(path)
        return original(path, metadata)

    monkeypatch.setattr(snapshot_cache, "_read_body", counting_read)

    latest = cache.latest(OCTOBER_URL)

    assert latest is not None and latest.body == _html("second")
    assert len(reads) == 1
    with pytest.raises(SnapshotCacheError, match="body is unreadable"):
        cache.history(OCTOBER_URL)


@pytest.mark.unit
def test_latest_still_checks_every_older_sidecar(tmp_path) -> None:
    cache = SnapshotCache(tmp_path)
    oldest = cache.write(OCTOBER_URL, _html("first"), _metadata(FIRST_FETCH))
    cache.write(OCTOBER_URL, _html("second"), _metadata(SECOND_FETCH))
    oldest.with_name(oldest.name + ".meta.json").unlink()

    with pytest.raises(SnapshotCacheError, match="no metadata sidecar"):
        cache.latest(OCTOBER_URL)


_KILLED_WRITER = """
import os
import sys
from datetime import datetime

import nba_data.scraping.snapshot_cache as snapshot_cache
from nba_data.scraping.cache import CacheFetchMetadata

original = snapshot_cache._publish


def publish_then_die(temp_path, final_path, what):
    if what == "snapshot file":
        os._exit(17)
    if sys.argv[4] == "hard-link":
        os.link(temp_path, final_path)
    else:
        original(temp_path, final_path, what)


snapshot_cache._publish = publish_then_die
url, fetched_at = sys.argv[2], datetime.fromisoformat(sys.argv[3])
snapshot_cache.SnapshotCache(sys.argv[1]).write(
    url, "<!DOCTYPE html><html>killed</html>", CacheFetchMetadata(fetched_at, 200, url)
)
"""


@pytest.mark.unit
@pytest.mark.parametrize("publication", ["native", "hard-link"])
def test_a_killed_writer_leaves_an_incomplete_write_that_recovery_clears(
    tmp_path, publication: str
) -> None:
    cache = SnapshotCache(tmp_path)

    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            _KILLED_WRITER,
            str(tmp_path),
            OCTOBER_URL,
            FIRST_FETCH.isoformat(),
            publication,
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert completed.returncode == 17, completed.stderr
    leftovers = cache.incomplete_writes(OCTOBER_URL)
    assert list(leftovers) == _files(tmp_path)
    # POSIX publication retains the metadata's temp name as a hard link;
    # Windows native publication renames it. Exercise both on Windows too.
    uses_hard_link = publication == "hard-link" or os.name != "nt"
    assert len(leftovers) == (3 if uses_hard_link else 2)
    sidecars = [path for path in leftovers if path.name.endswith("Z.html.gz.meta.json")]
    body_temps = [
        path
        for path in leftovers
        if ".html.gz." in path.name and ".meta.json." not in path.name and path.suffix == ".tmp"
    ]
    metadata_temps = [path for path in leftovers if ".meta.json." in path.name]
    assert len(sidecars) == 1
    assert len(body_temps) == 1
    assert len(metadata_temps) == int(uses_hard_link)
    if uses_hard_link:
        assert metadata_temps[0].samefile(sidecars[0])
    # Not a snapshot: readers see nothing.
    assert cache.latest(OCTOBER_URL) is None
    # The orphan sidecar refuses only its own timestamp.
    with pytest.raises(CacheWriteError, match="Refusing to overwrite"):
        cache.write(OCTOBER_URL, _html("retry"), _metadata(FIRST_FETCH))
    cache.write(OCTOBER_URL, _html("refetch"), _metadata(SECOND_FETCH))
    assert cache.incomplete_writes(OCTOBER_URL) == leftovers

    # Recovery (ADR 0022): with no writer running, delete the listed files.
    for path in leftovers:
        path.unlink()

    assert cache.incomplete_writes(OCTOBER_URL) == ()
    cache.write(OCTOBER_URL, _html("retry"), _metadata(FIRST_FETCH))
    assert [snapshot.body for snapshot in cache.history(OCTOBER_URL)] == [
        _html("retry"),
        _html("refetch"),
    ]


@pytest.mark.unit
def test_a_name_with_an_impossible_date_raises_a_cache_error(tmp_path) -> None:
    cache = SnapshotCache(tmp_path)
    cache.write(OCTOBER_URL, _html("x"), _metadata())
    stray = cache.directory_for_url(OCTOBER_URL) / "20261340T000000000000Z.html.gz"
    with gzip.open(stray, "wt", encoding="utf-8") as file:
        file.write(_html("stray"))

    with pytest.raises(SnapshotCacheError, match="not a valid fetch timestamp") as excinfo:
        cache.latest(OCTOBER_URL)

    assert isinstance(excinfo.value.__cause__, ValueError)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("damage", "cause"),
    [
        (lambda raw: raw[: len(raw) // 2], EOFError),
        (lambda raw: b"not gzip at all", gzip.BadGzipFile),
        (lambda raw: gzip.compress(b"\xff\xfe<html>"), UnicodeDecodeError),
    ],
    ids=["truncated", "not-gzip", "not-utf8"],
)
def test_an_unreadable_body_raises_a_cache_error(tmp_path, damage, cause) -> None:
    cache = SnapshotCache(tmp_path)
    path = cache.write(OCTOBER_URL, _html("x"), _metadata())
    path.write_bytes(damage(path.read_bytes()))

    with pytest.raises(SnapshotCacheError, match="body is unreadable") as excinfo:
        cache.latest(OCTOBER_URL)

    assert isinstance(excinfo.value.__cause__, cause)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("field", "value"),
    [("http_status", "200"), ("http_status", True), ("final_url", 123)],
)
def test_write_refuses_metadata_its_reader_would_reject(tmp_path, field: str, value) -> None:
    cache = SnapshotCache(tmp_path)
    metadata = _metadata()
    object.__setattr__(metadata, field, value)

    with pytest.raises(CacheWriteError, match="reader would reject"):
        cache.write(OCTOBER_URL, _html("x"), metadata)

    assert _files(tmp_path) == []


@pytest.mark.unit
def test_write_refuses_a_fetch_time_that_is_not_a_datetime(tmp_path) -> None:
    cache = SnapshotCache(tmp_path)
    metadata = _metadata()
    object.__setattr__(metadata, "fetched_at", FIRST_FETCH.isoformat())

    with pytest.raises(ValueError, match="must be a datetime"):
        cache.write(OCTOBER_URL, _html("x"), metadata)

    assert _files(tmp_path) == []
