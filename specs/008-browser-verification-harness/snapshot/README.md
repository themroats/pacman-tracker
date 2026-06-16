# Verification Snapshot Artifact

This folder holds the **frozen Seattle PostGIS snapshot** used by the local browser
verification harness (feature `008-browser-verification-harness`).

## What lives here

- `seattle.dump` — a `pg_dump` of `cities`, `neighborhoods`, and `street_segments`
  only (no user/activity/coverage tables, so no private data). **Generated locally,
  not committed** (it is gitignored) — each developer builds it once from their own
  PostGIS Seattle data. Re-seeding from the local dump is deterministic and never
  re-downloads from OpenStreetMap.

## How to (re)build it

From a PostGIS database already loaded with Seattle data (via
`python -m app.scripts.load_cities`):

```powershell
cd backend
python -m app.scripts.snapshot_verification build `
    --output ..\specs\008-browser-verification-harness\snapshot\seattle.dump
```

The resulting `seattle.dump` stays local (gitignored) — do **not** commit it.

> The `build` command uses host `pg_dump`. If you don't have PostgreSQL client
> tools installed, dump from the Docker DB container instead:
>
> ```powershell
> docker exec -e PGPASSWORD=pacman_dev pacman-tracker-db-1 pg_dump -U pacman -d pacman `
>     -Fc --no-owner --no-privileges -t cities -t neighborhoods -t street_segments -f /tmp/seattle.dump
> docker cp pacman-tracker-db-1:/tmp/seattle.dump .\specs\008-browser-verification-harness\snapshot\seattle.dump
> ```

## How to restore it

```powershell
cd backend
python -m app.scripts.snapshot_verification restore `
    --input ..\specs\008-browser-verification-harness\snapshot\seattle.dump `
    --database-url postgresql://pacman:pacman_dev@localhost:5432/pacman_verify
```

> Restore is **data-only** — it loads the baseline rows into tables created by
> `alembic upgrade head`, so run migrations on the verification database first.
> The launchers handle this ordering automatically.

The launcher `infra/verify-up.ps1` does this automatically when the verification
database is empty.
