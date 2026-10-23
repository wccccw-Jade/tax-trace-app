# UI redesign

Implemented using the UI/UX Pro Max skill, with the existing React/Vite stack and no additional dependencies.

## Changes

- Navy sidebar, grouped navigation, consistent controls, readable work surfaces and responsive layouts.
- Review overview focuses on finding progress and approved tax estimates. Full filing readiness remains separate.
- Searchable findings with attention, awaiting-review, approved and all filters. Plain-language explanations and explicit review actions retain links to the original evidence.
- Native modal details separate value review, questions/decisions and evidence. Linked records have a back path. Forms retain state between detail views; correction entry, technical JSON and history expand on demand.
- Client landing summary displays jurisdiction amounts instead of raw JSON.
- Evidence library reports the documents actually available in the current workspace, including replay-date restrictions.
- Existing correction, permission, collaboration, comparison and filing logic is preserved.

Design decisions: [MASTER.md](../design-system/miraflores/MASTER.md).

## Verification

- `npm run build --prefix frontend`: TypeScript and production build passed.
- `git diff --check`: passed.
- Local HTTP smoke checks: staff audit, available documents, review statuses, workpaper summary, claim/document traces, client summary and production frontend delivery passed.
- No workpaper approvals, corrections or filing actions were made during these checks.
- Browser preview was unavailable through the enabled computer-use tools. Responsive appearance and keyboard interactions still need an interactive visual review; these are implemented but not browser-verified.

Preview locally with `make dev`, then open http://127.0.0.1:5173.
