# Day 0–1 implementation status

## Implemented and checked

- FastAPI backend and React/TypeScript/Vite foundation, with dependency lockfiles and local startup instructions.
- PostgreSQL 17 managed by Docker Compose; initial Alembic migration and actual packet import succeeded.
- Original packet preserved with SHA-256; repeated import is idempotent.
- 74 documents, 3,012 extracted values, 1,877 return lines across three versions and 11,280 evidence edges. All source/input references resolve.
- Automatic source locators: 1,206 / 3,012 resolved. Unresolved values are reported. Manual-anchor API validates offsets and expected revisions; the selection UI is not built yet.
- Independent audit: 11 proposed discrepancies, with source references and tax-effect estimates. Open investigation leads remain listed in `audit-findings.md`.
- Eleven explicit arithmetic formulas reproduce v3. No formula inference or tax-engine rerun.
- Demo role sessions, server-side internal-route restrictions, sensitive-value masking and cleared-view logging.
- React findings queue, document search, role selector and simulated evidence drawer with field highlighting where anchors resolve.

## Verification

- Standalone audit: passed.
- Backend suite with `TEST_DATABASE_URL`: 8 passed, including actual PostgreSQL import/idempotence.
- Frontend: Node.js v24.22.0, npm 11.19.1, dependencies installed and `package-lock.json` generated. TypeScript check and Vite production build passed.
- Live HTTP checks through the frontend dev server: page loads, API proxy works, PostgreSQL ready, 74 documents, 11 findings, cleared staff access, Marcus Bell masking, client internal-access rejection, access-log entries, and manual-anchor stale-revision rejection.
- Static mount moved after all API routes so the production build does not shadow the manual-anchor endpoint. Route-authorization regression check added.
- No browser is attached to the agent session, so visual/UI interaction verification is not claimed.
- Backend/database persistence across a restart has not yet been checked.

A TestClient/httpx deprecation warning remains; tests pass.

## Local use

Node is installed through nvm. If `node` is missing from the terminal PATH:

```sh
source ~/.nvm/nvm.sh
nvm use
```

Then:

```sh
make db
make migrate
make import
make dev
```

Frontend: http://127.0.0.1:5173  
API docs: http://127.0.0.1:8000/docs

Use `make db-status`, `make db-logs`, and `make db-stop` to manage PostgreSQL. Data persists in the named Docker volume.

## Remaining foundation work

- Finish open audit leads and finalize the demo error list.
- Improve field/date mappings and build manual source-selection UI.
- Verify the interface visually and persistence across restart.
- Replay-aware evidence visibility and staff active dates remain unimplemented; no replay endpoint is exposed.

Verification/adjustment/approval writes, attachments/questions, sign-off invalidation and filing/export workflows belong to subsequent stories. No cloud deployment has occurred.
