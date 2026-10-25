# Day 9: hardening and submission documents

October 23, 2026. Local work implemented; actual Heroku deployment and manual browser verification remain incomplete.

## Completed work

- Preserved the existing import, masking, self-review, stale-write, policy/source invalidation, snapshot immutability, readiness inheritance, formula-registry and calculation-basis coverage.
- Added a private S3-compatible attachment adapter. Files remain behind the existing authenticated download routes; no public object URLs are generated. Tests cover storage requests, key boundaries, missing files and safe failure recovery.
- Hosted configuration normalizes Heroku database URLs for psycopg 3, requires SSL in production, rejects local-only production attachments, and uses secure/HTTP-only session cookies.
- Prepared `Procfile`, runtime version, root frontend build hook and an idempotent migration/import release command. The build is checked locally; a cloud release is not claimed.
- Implemented database/private-file backups, checksums and empty-target restore safeguards. A real local drill restored 11 tables, an attachment and a saved revision, and verified the restored immutable-snapshot trigger using disposable databases only.
- Improved keyboard paths: skip link has a focusable main target, historical/nonnumeric records open their evidence view directly, and the updates panel dismisses on Escape and returns focus to its button. Existing native modal containment, labels, status text and empty/error states remain.
- Finalized the submission documents below and a one-page, rendered/visually inspected PDF.

## Validation results

- **40 tests passed** with `TEST_DATABASE_URL` configured; none skipped in the full run.
- `npm run heroku-postbuild` passed from a clean locked frontend install after retrying with network access. `pip check`, offline migration SQL and `git diff --check` passed.
- The release command ran twice locally with migrations at head and the packet already present, demonstrating idempotence.
- Local `/api/health`, `/api/ready`, role switching, frontend delivery, full sales detail and genuine filing blockers passed. Three requests for all 295 sales rows took 118.2, 109.7 and 82.0 ms locally; this is not a hosted load test.
- The one-page PDF has exactly one page and its rasterized rendering was inspected for clipping, overlap and legibility.

## Documents

- One-page concept/model PDF: [miraflores-core-idea.pdf](../output/pdf/miraflores-core-idea.pdf); editable text: [core-idea.md](submission/core-idea.md).
- [Source-backed error report and UI paths](submission/error-report.md).
- [Tools and AI-use disclosure](submission/tools-and-ai.md).
- [Heroku deployment runbook](heroku-deployment.md).
- [Backup/restore procedure and drill](backup-and-restore.md).
- [Brief capability checklist](requirement-checklist.md).

## Remaining gates

**Heroku:** target app, attached Postgres, private bucket configuration and authenticated deployment access are missing. Heroku CLI is unavailable in the current environment. No app/add-on/bucket was created and no deployment, hosted persistence or live object-storage check is claimed. The deployment files and exact verification procedure are ready for the identified target.

**Browser:** Computer Use reports no browser/native app surface and a native-pipe startup error. Keyboard and visual behavior therefore remain implemented/code-reviewed but not interactively browser-verified. No alternative browser automation was used to bypass that limitation.

**Day 10:** the user still needs to record/upload the personal walkthrough and supply the video link. Final submission also needs the verified hosted app link.
