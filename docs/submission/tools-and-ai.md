# Tools and AI use

The prototype was developed with AI coding assistance through Codex, under the user's direction. AI helped read the supplied brief, inspect the invented JSON packet, propose the claims-and-proof model, draft source checks, implement backend/frontend workflows, write tests, and prepare these documents. UI/UX Pro Max guidance informed the interface redesign and readable typography. AI assistance is not represented as independent professional tax review.

The working stack is FastAPI, SQLAlchemy, Alembic and PostgreSQL, with React/TypeScript and Vite. Docker manages local PostgreSQL. S3-compatible storage is accessed through boto3. Python's Decimal is used for tax arithmetic; the supplied calculation rates and snapshots define the simulator's limits. ReportLab generates the one-page PDF and PyMuPDF renders it for visual inspection. These authoring libraries are not required by the hosted app.

## How AI-assisted findings were checked

- The original packet is retained with a SHA-256, and import tests check counts, references and idempotence.
- Findings are reproduced by deterministic source comparisons and explicit arithmetic in `backend/domain/audit.py`, rather than by trusting extraction confidence or engine diagnostics. The error report lists the exact supporting references and the UI path to inspect them.
- The formula registry must reproduce the supplied v3 values. Rate-based estimates are kept separate from exact line recomputation and payment corrections.
- Disposable PostgreSQL schemas exercise separation of duties, masking, stale-write rejection, source/policy invalidation, evidence-backed judgments, bulk undo, genuine filing blockers, rejected/accepted copies, immutable snapshots and exports.
- SDK stub tests check private object-storage requests, missing files and safe failure recovery without claiming a live cloud connection.
- A real local database/attachment restore drill checks table hashes, file bytes, saved revisions and the restored snapshot guard using disposable databases. No test proofs or approvals are copied into the live workspace.

## What is not claimed

No exhaustive tax-law validation, real authentication, generic OCR pipeline, real e-file/signature/payment, or tax-engine rerun is implemented. The dataset and simulated documents are invented. Browser keyboard/visual interaction and the hosted restart/redeployment check must be reported separately from automated backend/build success. Deployment cannot be called complete until the target Heroku app, Postgres and private bucket are connected and verified. The user must record the final personal walkthrough video.
