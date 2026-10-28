# Tax Workpaper

An evidence-first workspace for reviewing a tax return: trace a number to its source, explain a correction, record who checked it, and see what still needs attention.

This is a personal software project built around a fictional household's 2025 U.S. federal and California returns. It explores how tax review can work as a connected set of claims, evidence and decisions, with a shared history across preparers, reviewers and clients.

## How it works

Every return line is a claim backed by evidence. Opening a claim connects its value to source documents, extracted fields, related calculations and review history. A correction preserves the original value and requires supporting evidence, verification and independent approval before it affects the approved workpaper.

If supporting evidence changes, the earlier approval can become stale and the work reopens. Filing readiness is calculated from the remaining review work, rather than set with a checkbox.

For example, the sample data includes bank interest reported on two statements. You can inspect both sources, document the duplicate, propose a correction, and switch to an independent reviewer to approve it. Both the original and approved values remain visible.

## Features

- **Source tracing:** follow return lines to simulated document pages and highlighted fields, inspect where evidence is used, and save manual source anchors.
- **Review workflows:** propose and verify corrections, record judgments with authority and rationale, enforce independent review, and reopen approvals when their supporting evidence changes.
- **Client and team collaboration:** ask questions, attach private supporting files, assign work, track deadlines, and receive in-app updates. Internal threads stay separate from the client portal.
- **Comparisons and scenarios:** compare return versions and prior-year values, track changes since your last review, and preview estimated effects before proposing a change.
- **Detailed tax views:** inspect business income, investment sales, depreciation, rentals, K-1 income, basis, retirement, foreign items, deductions, credits, payments, state allocation and carryovers. Eligible sales can be verified in bulk with undo.
- **Simulated filing:** check readiness, collect approvals, freeze a hashed submission, replay rejection and acceptance, preserve earlier copies, create amendment branches, and export a self-contained examination record.
- **Workspace controls:** version firm standards, mask sensitive fields by clearance, log access, track time against budget, search records, and manage retention eligibility and holds.

The sample packet contains 74 fictional documents, 3,012 extracted values and three computed return versions. Some records deliberately disagree. Later evidence becomes available as the filing timeline advances.

## Scope and limitations

This is a prototype for invented data, not a production tax-preparation service.

- The role switcher demonstrates server-side permissions; it is not production authentication or tenant isolation. Use the supplied fictional data, not real client records.
- Documents are simulated from supplied text. There is no OCR pipeline or original document imagery.
- A small formula registry recomputes supported arithmetic. Other affected lines retain explicit calculation labels, and tax effects use supplied rates as estimates. This does not replace a tax engine or professional tax review.
- Filing, signatures, agency responses and payments are simulated. Nothing is transmitted to a tax agency or paid externally.
- Missing evidence and incomplete review remain open. Importing the dataset does not approve the return.

## Tech stack

| Layer | Technology |
| --- | --- |
| Frontend | React, TypeScript, Vite |
| API | Python, FastAPI |
| Persistence | PostgreSQL, SQLAlchemy, Alembic |
| Local database | PostgreSQL 17 through Docker Compose |
| Attachments | Private local files or S3-compatible object storage |
| Testing | pytest, FastAPI test client, PostgreSQL integration tests |

## Run locally

### Prerequisites

- Python 3.15, matching `.python-version`.
- Node.js 24 and npm.
- Docker with Docker Compose, running locally.
- Make and a POSIX-compatible shell.

From the repository root:

```sh
python3 -m venv .venv
cp .env.example .env
make install
make db
make migrate
make import
make dev
```

Open **http://127.0.0.1:5173** and choose a demo identity in the header. The API documentation is at **http://127.0.0.1:8000/docs**.

`make dev` runs the API and frontend together. PostgreSQL runs in Docker; you do not need a native PostgreSQL installation. The default database connection uses `localhost:5432`, and the credentials in `.env.example` are for local development.

The import preserves the original packet and its SHA-256. Re-importing the same packet is idempotent and does not reset saved review work.

### Try a review

1. Select **Priya Raman**, the preparer, and open finding **E1** in the review workspace.
2. Follow its evidence links to compare the two bank-interest statements.
3. In the claim's **Review value** view, propose a corrected value of `0`, explain the duplicate, and cite `D28` and `D29`.
4. Verify the proposed value against the evidence.
5. Switch to **Daniel Ortiz**, the reviewer, and approve the correction independently.

The original value remains available, while the approved workpaper reflects the correction. Trying to approve your own preparation work is blocked. Other sample identities demonstrate partner approval, client questions, administration and limited data clearance.

### Common commands

| Command | Purpose |
| --- | --- |
| `make dev` | Start the local API and frontend |
| `make db` | Start PostgreSQL and wait for it to become healthy |
| `make db-status` | Show database container status |
| `make db-logs` | Show recent database logs |
| `make db-stop` | Stop PostgreSQL while preserving its data |
| `make migrate` | Apply database migrations |
| `make import` | Import the sample packet without duplicating it |
| `make audit` | Generate source-check results and an audit report |
| `make refresh` | Refresh derived checks and automatic anchors, preserving manual work |
| `make build` | Type-check and build the frontend |
| `make backup` | Back up the database and referenced attachments |
| `make backup-drill` | Verify recovery using disposable local databases |

Database data persists in the Docker volume. Removing that volume with `docker compose down -v` deletes the local database.

## Tests

Run the full suite against local PostgreSQL:

```sh
make db
TEST_DATABASE_URL=postgresql+psycopg://miraflores:miraflores@localhost:5432/miraflores make test
make build
```

PostgreSQL tests create and remove isolated schemas. They do not insert test approvals into the working application database. Without `TEST_DATABASE_URL`, database-dependent tests are skipped; `make test` still runs the remaining tests.

Coverage includes import integrity, source references, masking, separation of duties, revision conflicts, stale approvals, bulk undo, calculation labels, filing readiness, immutable snapshots, exports and private attachment storage.

## Configuration and deployment

`.env.example` documents the local configuration. The main settings are:

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | PostgreSQL connection |
| `PACKET_PATH` | Sample packet location |
| `ATTACHMENT_BACKEND` | `local` or `s3` |
| `ATTACHMENT_DIR` | Local private attachment directory |
| `APP_ENV` | `development` or `production` |
| `S3_BUCKET`, `S3_REGION`, `S3_ENDPOINT_URL`, `S3_PREFIX` | Private object-storage configuration |

Keep credentials in environment variables or the hosting platform's secret store. Local settings, attachments and backups are ignored by Git.

The repository includes a Heroku build hook, `Procfile` and migration/import release command. Production configuration requires private object storage and database SSL; dyno-local files are not used for durable attachments. Deployment configuration is included, but hosted operation must be verified on the target services.

For a single-origin local build:

```sh
make build
.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
```

FastAPI serves the built frontend from `frontend/dist`. See the [Heroku deployment guide](docs/heroku-deployment.md) and [backup and restore guide](docs/backup-and-restore.md) for operational details.

## Project structure

```text
backend/          API routes, domain logic, persistence and storage
frontend/         React interface
migrations/       Alembic database migrations
scripts/          Audit, development, release and recovery utilities
tests/            Domain, API and PostgreSQL tests
docs/             Design notes, walkthroughs and operational guides
output/pdf/       One-page concept and data-model document
```

## Design notes and background

- [Core idea and data model](docs/submission/core-idea.md)
- [One-page design overview](output/pdf/miraflores-core-idea.pdf)
- [Source-backed findings and how the interface surfaces them](docs/submission/error-report.md)
- [Tools and AI-use disclosure](docs/submission/tools-and-ai.md)

The project began as an implementation of the Miraflores tax-workpaper case study and is now maintained as an independent personal project. The fictional household and sample packet come from that exercise. This repository is not an official Miraflores product and does not imply affiliation or endorsement.
