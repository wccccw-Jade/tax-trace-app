# Miraflores workpaper

Day 0–1 foundation for the Okafor–Lindqvist case study. Local development only; no deployment has been performed.

## Prerequisites

- Python 3.11+ and a virtual environment (`.venv` already exists in this checkout).
- Node.js 22.12+ (or Node 24 LTS) and npm for React/Vite.
- Docker Desktop (running), including Docker Compose. PostgreSQL 17 runs in the `db` container; no native PostgreSQL installation is needed.

Node.js 24 and the frontend dependencies are installed; the TypeScript/Vite production build passed and `frontend/package-lock.json` is available. Docker PostgreSQL is running with the imported packet. All eight backend tests passed previously with PostgreSQL, and live HTTP checks verified the frontend/API connection, role switching, masking and database readiness. Visual browser verification remains pending because no browser is attached to the agent session.

## Local setup

```sh
python3 -m venv .venv
cp .env.example .env
make install
make db
make migrate
make import
make dev
```

Open **http://127.0.0.1:5173**. API docs are at **http://127.0.0.1:8000/docs**. Choose a demo identity from the header. Role switching requires a migrated PostgreSQL database. The API returns a setup message if the database is unavailable.

`make db` starts PostgreSQL through Docker Compose and waits for it to be healthy. Data lives in the named `postgres_data` volume and survives container stops/recreation. The app runs on your Mac and connects at `localhost:5432` using `.env.example`. The example credentials are for localhost development only.

Database management:

```sh
make db-status  # container health and port
make db-logs    # recent PostgreSQL logs
make db-stop    # stop PostgreSQL, preserving data
make db         # start again
```

Keep the Docker volume to retain your work; `docker compose down -v` deletes database data.

`make install` installs pinned backend dependencies and frontend dependencies. `frontend/package-lock.json` records the installed frontend versions; use `npm ci` inside `frontend/` for a clean reproducible install.

If Node was installed with nvm, activate it in your terminal before running Make commands:

```sh
source ~/.nvm/nvm.sh
nvm use
```

`make migrate` applies Alembic migrations. `make import` preserves the original JSON and SHA-256, adds version-scoped claims and a bidirectional evidence index, and is idempotent for the same packet hash. It does not edit the fixture or apply proposed corrections. Local `.env`, attachments and generated audit output are ignored by Git.

## What works in this foundation

- Standalone packet audit, without a database: `make audit` generates `var/audit.json`.
- Typed reference resolution, including prior-year/agency JSON pointers, parameters, assets and version-scoped lines.
- Conservative source locators, with an explicit unresolved state rather than an invented highlight.
- Small explicit arithmetic registry, tested against v3. It does not rerun the tax engine.
- PostgreSQL schema/migration and transactional packet import code.
- API for persisted findings, documents, trace links, role switching, client summary and administrator access logs.
- Server-side masking for uncleared actors; clients are denied internal workpaper routes. Cleared internal views generate safe access-log entries.
- React foundation: role selector, independent findings queue, document search and evidence drawer. Requires Node and PostgreSQL to run end to end.

The demo role selector intentionally permits selecting any fixture identity. It demonstrates authorization after identity selection; it is not authentication for real client data. Do not deploy real records with this mechanism.

Manual source anchoring has an API but no selection UI yet. Replay-aware evidence availability, adjustment/verification workflows and filing are not implemented yet. They remain follow-up tasks in `plan.md`.

## Checks

```sh
make audit
make test
.venv/bin/alembic upgrade head --sql
make build
```

Domain/API tests run without PostgreSQL. The integration test requires a disposable test database and creates/removes its own random schema:

```sh
TEST_DATABASE_URL=postgresql+psycopg://miraflores:miraflores@localhost:5432/miraflores .venv/bin/python -m pytest -m postgres -q
```

Without `TEST_DATABASE_URL`, that test is skipped, not reported as passing. It checks actual PostgreSQL import counts and idempotence. Add the production migration/API persistence check to the local verification once PostgreSQL is available.

For a single-origin build, run `make build`, then `.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000`. FastAPI serves only `frontend/dist`, never the repository or original packet. Restart the backend after building so it detects the build output.

## Deployment later

Heroku setup is deferred until the prototype is ready. Use Heroku Postgres plus private object storage for attachments; never rely on dyno files for durable data. `DATABASE_URL` and attachment configuration are environment based. No Heroku app, account or paid service was created.

## Sources and tools

- Product scope: `plan.md` and the supplied case-study PDF.
- Fixture: `okafor_lindqvist_2025_packet.json`, unchanged.
- Implementation uses FastAPI, SQLAlchemy, Alembic, React and Vite. AI assisted code/audit drafting; automated checks are documented in `docs/day-0-1-status.md`.
- Setup references: [Vite guide](https://vite.dev/guide/), [FastAPI tutorial](https://fastapi.tiangolo.com/tutorial/), [SQLAlchemy ORM guide](https://docs.sqlalchemy.org/en/21/orm/quickstart.html).
