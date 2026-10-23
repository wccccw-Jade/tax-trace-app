# Miraflores workpaper

Day 0–1 foundation, Stories A–E and the Day 7–8 breadth pass for the Okafor–Lindqvist case study. Local development only; no deployment has been performed.

## Prerequisites

- Python 3.11+ and a virtual environment (`.venv` already exists in this checkout).
- Node.js 22.12+ (or Node 24 LTS) and npm for React/Vite.
- Docker Desktop (running), including Docker Compose. PostgreSQL 17 runs in the `db` container; no native PostgreSQL installation is needed.

Node.js 24 and the frontend dependencies are installed; the TypeScript/Vite production build passed and `frontend/package-lock.json` is available. Docker PostgreSQL is running with the imported packet. All 35 backend/PostgreSQL tests passed, and live HTTP checks verified the frontend/API connection, role switching, masking and database readiness. Browser visual verification remains blocked because Computer Use permission is not granted. Saved source anchors, revisions, sessions and import records were verified after restarting both the app and PostgreSQL.

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

`make refresh` regenerates the derived audit and automatic locators for the existing import without overwriting manual anchors or changing original packet data. `make audit` regenerates the standalone JSON and Markdown findings report.

The demo role selector intentionally permits selecting any fixture identity. It demonstrates authorization after identity selection; it is not authentication for real client data. Do not deploy real records with this mechanism.

Manual source anchoring is available in the evidence drawer: open a document or page, select an extracted field, select the exact supporting text, then choose **Save source anchor**. The actor, time and revision are recorded; this does not mark the value verified. Automatic mappings locate 2,672 / 3,012 values, with explicit unresolved states for the rest.

The Day 0–1 audit identified 14 proposed discrepancies and documented all original investigation leads. Remaining tax judgments are explicitly assigned to later workpaper workflows, not assumed resolved.

Story A adds evidence-bound verification, correction proposals, independent approval/rejection, document dispositions and an approved-only estimated summary. Story B adds a business-income bridge, partner approval and reopening when supporting evidence changes. Story C adds client questions, private attachments, reviewed judgments and reversible bulk verification. Story D adds version comparison, per-user change tracking, independent what-if previews and prior-year variance explanations. Story E adds computed readiness, exact-draft approvals, immutable simulated submissions, rejection/correction/acceptance, exports, amendment branches and post-filing models. Day 7–8 adds generated tax views, team coordination, firm controls, search, completeness and quality review. Production deployment and final submission artifacts remain follow-up tasks in `plan.md`.

## Story A: trace and correct

Update the schema before running the new workflow:

```sh
make db
make migrate
make dev
```

1. Select **Priya Raman**. Open **E1: Duplicate Northlake sweep interest** and inspect the D28/D29 evidence links.
2. Open D29 (via the evidence library or its page's document link). Set its disposition to **duplicate**, original document **D28**, and record the reason. This alone does not change the return.
3. Reopen E1. Propose corrected value **0**, explain why the interest is already included in D28, and cite D28 and D29. Save the proposal. It persists, but the approved value remains **1,840**.
4. In the claim panel, record a verification of the **proposed value**, with the firm method and what you checked. Priya cannot approve her own work.
5. Switch to **Daniel Ortiz**, reopen E1, enter a review conclusion, and approve. You can also reject a proposal without changing the approved return.
6. The queue shows **Approved correction**. Original engine value **1,840** remains visible, approved workpaper value is **0**, and the summary includes the correction once: estimated federal tax change **−640**, California **−127**.

The summary excludes pending, rejected and reopened corrections. Only registered arithmetic is recomputed; unsupported downstream lines retain their original values with an `affected` label. Review/verification history records actors, evidence, times, reasons and status. Changed source revisions invalidate evidence-bound verification. Approvals with a tax effect over $1,000 require an independent partner.

Tests use isolated PostgreSQL schemas and do not pre-approve corrections in your demo database. The later filing, review-note and amendment/export workflows are described below.

## Story B: business income and partner review

Open **Business income** for a plain-language explanation of the duplicated $12,400 payment, source links and the books-to-tax bridge. Priya proposes revenue of $151,300 and verifies the evidence; Helen approves because the estimated tax effect exceeds $1,000. A later D15 disposition change reopens the approval and excludes the correction from the summary until fresh verification and approval. The prior approval stays in history.

See [the complete walkthrough](docs/day-3-4-status.md) for steps and expected values. Changes to cited source anchors also reopen affected approvals. Unrelated corrections remain approved. SE tax and QBI are included once in the combined estimate; their actual return lines remain marked affected.

## Story C: client evidence, judgments and checked sales

Run `make migrate` and restart the backend. Staff can ask a client from a claim; the assigned client answers and attaches files in their portal. Answers become evidence, while an independently reviewed decision records the chosen treatment, alternatives, authority and rationale. E3 and C6 corrections are reviewed with their decisions. A request for more evidence keeps the underlying issue open.

**Sales detail** checks each broker row against the current printed statement. It currently offers 159 eligible rows, keeps exceptions visible, and saves bulk verification as one operation with whole-batch undo. Undo preserves the original verification history.

See [the plain-language walkthrough](docs/day-4-5-status.md) for E3, C6 and bulk verification. Attachments are stored privately in `ATTACHMENT_DIR` (default `var/attachments`); include that directory in local backups. Downloads require client ownership or staff clearance. Private object storage remains a prerequisite for Heroku deployment.

## Story D: history, what-if and prior year

Run `make migrate` and restart the backend. **History** compares engine versions and the approved workpaper, including source changes, and keeps an explicit per-user “seen” marker. **What-if** shows all five supplied alternatives against v3 independently, plus read-only numeric previews from v3 or the approved workpaper. Supported previews can become proposals through the existing review workflow.

**Prior year** applies the firm's combined percentage/dollar threshold, treats zero and missing values explicitly, and saves explanations against the values they covered. Changed values make earlier explanations stale. See [the walkthrough](docs/day-5-6-status.md) for steps and expected results. Migration `0004` persists staff activity markers; this story remains local-only.

## Story E: readiness, frozen filing and after

Run `make migrate` and restart the backend. **Readiness & filing** lists genuine claim, document, diagnostic, question and checklist blockers. Once those are resolved, independent staff sign-offs, explicit partner acceptance of estimated computation and both clients’ exact-draft authorizations permit a simulated submission. Clients use **Approve & copies**.

Each attempt creates an immutable hashed snapshot. The scripted rejection, reviewed identity correction, linked resubmission and separate agency acceptances preserve earlier copies. Accepted records support HTML client copies, examination ZIPs with checksums, separate amendment branches and snapshot-based payment/carryforward/planning models.

See [the complete walkthrough](docs/day-6-7-status.md). Migration `0005` adds database protection for frozen snapshots. The live workspace starts blocked; automated tests use synthetic remaining-scope proofs only in isolated test schemas. Nothing is transmitted or paid externally, and no official Form 1040-X is generated.

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

Without `TEST_DATABASE_URL`, that test is skipped, not reported as passing. It checks actual PostgreSQL import counts and idempotence. The PostgreSQL/API checks also cover successful manual-anchor saves, invalid selections, revision conflicts, role restrictions and preservation of manual anchors during refresh.

For a single-origin build, run `make build`, then `.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000`. FastAPI serves only `frontend/dist`, never the repository or original packet. Restart the backend after building so it detects the build output.

## Persistence check

The local app and database restart check is reproducible:

```sh
.venv/bin/python scripts/check_persistence.py prepare
# Restart make dev and the Docker database, then:
.venv/bin/python scripts/check_persistence.py verify
```

This saves a manual source anchor for the Swedish interest field and a local demo session, then verifies their revisions/content and packet counts after restart. Temporary check state stays in ignored `var/`.

## Deployment later

Heroku setup is deferred until the prototype is ready. Use Heroku Postgres plus private object storage for attachments; never rely on dyno files for durable data. `DATABASE_URL` and attachment configuration are environment based. No Heroku app, account or paid service was created.

## Sources and tools

- Product scope: `plan.md` and the supplied case-study PDF.
- Fixture: `okafor_lindqvist_2025_packet.json`, unchanged.
- Implementation uses FastAPI, SQLAlchemy, Alembic, React and Vite. AI assisted code/audit drafting; automated checks are documented in `docs/day-0-1-status.md`.
- Setup references: [Vite guide](https://vite.dev/guide/), [FastAPI tutorial](https://fastapi.tiangolo.com/tutorial/), [SQLAlchemy ORM guide](https://docs.sqlalchemy.org/en/21/orm/quickstart.html).

## Day 7–8: tax views and workspace controls

Restart `make dev`. No additional migration is required beyond `0005`.

- **Tax views:** eleven read-only tax/area views with claim/source drill-down, including the D73 state-wage reconciliation. Supported allocation changes use an explicit judgment, verification and independent review.
- **Team & deadlines / Updates:** durable assignments, packet deadlines, time vs budget, polling notifications and recoverable two-session conflicts.
- **Completeness:** documents, 13 considered areas and six outside/related responsibilities. Missing coverage blocks original-return filing; scope acknowledgments never verify claims automatically.
- **Firm standards:** Jo edits versioned methods, thresholds, required steps and retention; relevant reviews go stale. Retention-only changes preserve tax review. Administrators can inspect logs and set retention holds; deletion is disabled.
- **Questions:** assigned clients or colleagues can answer with files as evidence. Internal threads remain private from clients; material staff contributors cannot approve their own work.
- **Search / Quality review:** clearance-aware, replay-aware search and immutable submitted-copy review. Sam becomes active on January 4, 2027; quality findings never change the frozen return.

See [the walkthrough and limitations](docs/day-7-8-status.md) and [brief coverage checklist](docs/requirement-checklist.md). The live workspace retains genuine open review work and no test approvals are copied into it.
