# Backup and recovery

Run backups after every approved acquisition, database load, model registration
or prediction write, and before a persistent migration. Stop writers first:
`pg_dump` is transactionally consistent, but the database and filesystem are not
one coordinated snapshot. Backing up real data needs the owner's direct
instruction naming the database and destination. This procedure grants no
approval for scraping or migrating `nba`.

## Create and verify

From the repository root with Docker Compose's `postgres` service running:

```powershell
uv run python scripts/backup_database.py create --database nba --destination D:/nba-backups
```

The destination must resolve outside the worktree; choose a separate physical
disk. Each run creates a new `nba-<UTC timestamp>-<random suffix>/` directory:

- `database.dump`: custom-format `pg_dump`, streamed as binary bytes directly
  from the container. No PowerShell output redirection is involved.
- `data/raw/`, `data/models/`, `reports/`: complete copies of all three existing
  source directories, including snapshot caches and model evaluation evidence.
- `dump.list`: `pg_restore --list` output.
- `manifest.json`: relative paths, sizes and SHA-256 for every asset and the
  dump, plus the database name and UTC creation time.

The command rehashes source and destination and refuses a changed source,
missing/extra files, links/junctions, or a content mismatch. It never overwrites
an older backup or propagates source deletions into it. Eight workers bound
small-file I/O. Required source directories must exist, even if empty.

Exit 0 and `Verified backup:` identify a successful run. Interrupted/failed
runs retain their partial directories; they are not usable backups. A manifest
must parse and pass verification, not merely exist. Raw manifests, dumps and
copied assets stay outside Git.

To recheck a completed snapshot, substitute its actual directory:

```powershell
uv run python scripts/backup_database.py verify --backup D:/nba-backups/nba-<timestamp>-<suffix>
```

Add `--compare-source` immediately after creating a backup to also compare all
asset paths and hashes against the current worktree. Later, a legitimate new
acquisition/report can make this comparison fail while the historical backup
remains valid. Verification detects corruption; it is not an authenticity check
against someone who can rewrite both the data and manifest.

There is no scheduler or automatic retention. Execute this procedure at the
events above, keep previous verified snapshots, and check capacity on the backup
disk. This local second disk does not cover loss of the entire machine.
Credentials and `.env` are deliberately excluded: retain any non-default restore
credentials separately through the owner's normal secret-management process.

## Restore rehearsal

An archive listing is not a restore test. Rehearse after the first backup, after
a PostgreSQL major-version change, and periodically thereafter. Restore only
into a uniquely named disposable database; never use `--clean` on `nba`.

1. Verify the snapshot as above. For an older standalone dump, compare its hash
   with the recorded run first. Record its path, hash and PostgreSQL version.
2. Generate a name such as `nba_test_restore_<random UUID>`. Confirm it is absent.
   Create it with `docker compose exec -T postgres createdb -U nba --template
   template0 <scratch-name>`; abort if creation fails. Keep that exact name for
   all following commands and cleanup.
3. Stream the dump to `pg_restore` with binary Python file handles. For example,
   save this short script outside Git, replace the two placeholders, then run it
   with `uv run python <script>`:

   ```python
   import subprocess
   from pathlib import Path

   scratch = "<scratch-name-created-in-step-2>"
   assert scratch.startswith("nba_test_restore_") and scratch.isidentifier()
   with Path("<verified-backup>/database.dump").open("rb") as stream:
       subprocess.run(
           ["docker", "compose", "exec", "-T", "postgres", "pg_restore",
            "--exit-on-error", "--no-owner", "--no-privileges", "-U", "nba",
            "--dbname", scratch], stdin=stream, check=True, timeout=600,
       )
   ```

4. Read `alembic_version` and representative table counts on the scratch copy.
   Compare with the acquisition/load evidence associated with that backup.
   Check games, both game-stat tables, players and seasons at minimum.
5. If the restored version is behind head, select its pending supported
   revisions explicitly in the [migration preflight](MIGRATION_HEAD_HANDOVER.md#step-2--preflight).
   Unsupported revisions need manual inspection and a documented rehearsal.
   Run Alembic with a **child-process** `DATABASE_URL` pointing at the scratch
   database on the same server. Never change `.env` for a rehearsal. Compare
   all existing `core`/`stats` table counts before and after, check the expected
   schema changes, and run the readiness probe against that scratch target.
6. Dispose all scratch connections. Drop only the database whose creation
   succeeded in step 2: `docker compose exec -T postgres dropdb -U nba
   <scratch-name>`. Confirm it is absent and `nba` remains at its original
   revision and counts. Record the result in the handover and task evidence.

Restore files by verifying the asset manifest, then copying the chosen snapshot
to a fresh directory. Compare every relative path and SHA-256 again before using
it as a cache/model root. Overwriting real data requires a separate owner decision.

## First recovery evidence — 2026-11-11

Under the owner's instruction to implement all six review findings, the
off-disk `nba-before-0010.dump` was read back from `D:/nba-backups/` (MD5
`af0c75e2e9297858df3161945780364e`) and restored with `--exit-on-error` into
`nba_test_f8022_88b5e15a7bba`. It restored at `0009_games_and_box_scores`.
The container and TCP migration connection were checked to name the same
PostgreSQL cluster before starting.

The selected preflight checks for `0010`–`0012` passed. Alembic upgraded the copy
to `0012_ml_predictions`; all 43 existing `core`/`stats` table counts were
identical before and after. Representative counts: 14,435 games, 28,870 team
lines, 474,309 player lines, 2,693 players and 27 seasons. The `ml` schema had
two tables, the redundant index and `players.slug` were absent, and the
readiness service returned `ready`. The scratch database was then dropped.

The repeatable command then produced
`D:/nba-backups/nba-20261111T200805Z-1cde3c08/`: 32,806 raw files
(1,215,350,451 B), 2 model files (6,856 B), and 312 reports (1,885,803,963 B).
Every relative path and SHA-256 matched the source. The current-head dump is
32,809,173 B, SHA-256
`511b946512c1e23f31989097d8a0f7391267ce5df8b2eb37b7398557dd0501e0`.
It also restored with `--exit-on-error` into `nba_test_f8022_2e880e8212f5`,
at `0012` with the same 43 core/stats table counts and readiness `ready`;
that scratch database was dropped too. A final read of the persistent `nba`
confirmed `0012`, unchanged game/player-line counts, and HTTP readiness 200.

The original flat copy under `D:/nba-backups/data/` was independently compared
against the source by relative path and SHA-256 too: all 32,806 raw files and
both model files match, not just their counts and total bytes.

An interrupted performance trial left
`D:/nba-backups/nba-20261111T200752Z-1002d133/` without a completed manifest.
It is a partial run, not a verified backup; the successful directory above is
the recovery source. No previous backup was overwritten or deleted.
