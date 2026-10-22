# Day 0–1 implementation status

Implementation and automated verification are complete. The one remaining verification gate is a visual browser walkthrough, blocked by Computer Use permissions. No visual acceptance is claimed and no cloud deployment occurred.

## Completed

- FastAPI backend, React/TypeScript/Vite frontend, locked dependencies, local startup commands and environment configuration.
- PostgreSQL 17 managed by Docker Compose; actual migrations and packet import completed.
- Original packet/hash preserved; 74 documents, 3,012 extracted values, 1,877 version-scoped return lines and 11,280 evidence edges. All references resolve.
- Automatic source anchors resolve 2,672 / 3,012 values. Lot/trip scopes handle repeated amounts and dates. The other 340 remain explicitly unresolved, with manual anchoring available.
- Manual source-selection UI: document/page → extracted field → select exact source text → save. Actor, time, quote, revision and audit event persist. Saving an anchor does not verify or approve the value.
- API conflict and permission checks; sensitive pages require clearance for manual anchoring. Client and administrator tax-preparation restrictions are enforced.
- Derived-data refresh preserves manual anchors and immutable packet data; the on-screen locator count reflects persisted records.
- Audit: 14 proposed discrepancies and documented dispositions for all 15 original leads. Meridian M18 is on unextracted page 32; replacement statement usage and S-corporation opening basis are reconciled. Remaining tax judgments are explicit later-story tasks, not assumed answers.
- Frozen initial demo sequence: E1 duplicate interest; E4 gross receipts/partner threshold; E3 vehicle gift judgment; E12 missing supplemental lot; crypto C6 evidence judgment.
- Eleven explicit arithmetic formulas reproduce v3; no formula inference or tax-engine rerun.
- Demo roles, internal-route restrictions, sensitive-value masking and cleared-view audit logging.

## Verification performed

- Standalone audit and reproducible Markdown report: passed (`make audit`).
- PostgreSQL/domain/API suite: **10 passed**, including real import/idempotence, manual save, invalid range, stale revision, clearance restrictions, client denial and preservation during derived-data refresh.
- TypeScript and Vite production build: passed (`make build`).
- Local app and PostgreSQL were stopped/restarted. Saved manual anchor, revision, demo session, original hash and import counts survived (`scripts/check_persistence.py prepare/verify`).
- Original packet unchanged; no corrections or approvals applied.
- Computer Use inventory found Chrome, but attempting inspection returned **“Computer Use permissions are not granted.”** Visual layout and mouse selection behavior remain unverified. No alternate browser automation was used to bypass that restriction.

The installed TestClient/httpx combination emits a deprecation warning; tests pass.

## Local use

```sh
make db
make migrate
make import
make refresh
make dev
```

Frontend: http://127.0.0.1:5173  
API docs: http://127.0.0.1:8000/docs

Select Priya, open **Evidence library**, choose a document/page and one of its extracted fields, then select text in the simulated source and save the anchor. The Swedish interest field (`D36` → `ev-0960`) is a simple example. Reload to inspect the saved quote/actor/time. Marcus sees masking and cannot anchor a page containing masked data. Clients cannot access internal workpaper records.

## Remaining gate and next story

- Visual browser walkthrough once Computer Use permission is enabled (or user checks it locally).
- Then Story A: verification methods, original-preserving adjustments and independent reviewer approval.

Replay, questions/attachments, broader CPA views, sign-off invalidation and filing/export remain later stories. Unresolved anchors and tax judgments continue as real workpaper tasks; they are not silently marked complete.
