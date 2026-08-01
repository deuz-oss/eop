# EOP API

Enterprise Operations Platform Backend API.

## Database Migrations

Migrations are managed with [Alembic](https://alembic.sqlalchemy.org/), configured for the
project's async SQLAlchemy engine. Migration scripts live in `alembic/versions/` and
autogenerate compares the database against `eop_api.db.base.Base.metadata`.

The database URL is read from the app's own settings (`DATABASE_URL`, see `.env`) rather than
being duplicated in `alembic.ini` — there is a single source of truth for connecting to the
database.

All commands below can be run directly with `uv run alembic ...` from `services/api/`, or via
the `make` targets from the repository root (which `cd` into `services/api` for you).

### Create a migration

After changing a model, generate a migration by diffing the models against the database:

```bash
make revision MESSAGE="add employee table"
# equivalent to:
# cd services/api && uv run alembic revision --autogenerate -m "add employee table"
```

Autogenerate is a starting point, not the final word — always open the generated file in
`alembic/versions/` and review/adjust it before committing.

### Upgrade

Apply all pending migrations:

```bash
make migrate
# uv run alembic upgrade head
```

### Downgrade

Roll back the most recently applied migration:

```bash
make downgrade
# uv run alembic downgrade -1
```

### Inspect state

```bash
make current   # show the currently applied revision
make history    # list all revisions
```

### Common workflow

1. Change a SQLAlchemy model (imported under `eop_api.models`, registered on `Base.metadata`).
2. `make revision MESSAGE="describe the change"` to autogenerate a migration.
3. Review the generated file in `alembic/versions/`.
4. `make migrate` to apply it locally and confirm it works.
5. `make downgrade` to confirm the downgrade path also works, then `make migrate` again.
6. Commit the model change together with its migration file.

### Running against a local (non-Docker) database

The default `DATABASE_URL` uses the Docker Compose service hostname `postgres`, which only
resolves inside the Compose network. To run Alembic against Postgres from your host machine
(with only `docker compose up -d postgres` running), point `DATABASE_URL` at `localhost`
instead:

```bash
DATABASE_URL="postgresql+asyncpg://eop:eop@localhost:5432/eop" uv run alembic upgrade head
```

Alternatively, run migrations inside the `api` container, where `postgres` resolves normally:

```bash
docker compose exec api alembic upgrade head
```
