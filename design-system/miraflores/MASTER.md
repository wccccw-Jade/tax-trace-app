# Miraflores interface design

A focused workspace for reviewing a tax return. Users should understand the next action before learning tax terminology.

## Direction

Use a calm, minimal professional interface: navy navigation, white work surfaces, blue actions and clear typography. Group destinations by work, comparison and completion. Keep technical references secondary to task descriptions.

UI/UX Pro Max searches informed this review. The professional dashboard search supplied a suitable minimal style and navy/blue palette. Its marketing-page layout recommendation did not fit this application; the enterprise retry also returned a marketing layout. The application layout below is a deliberate fallback designed for the existing workflows, not a generated layout match. React guidance verified native semantics and modal focus management.

## Tokens

- Main text: `#172b40`; secondary text: `#526478`.
- Navigation: `#111f32`; navigation text: `#bdcbdc`.
- Action: `#0369a1` with white text; pale action surface: `#eaf4fb`.
- Page: `#f5f7fa`; cards: white; border: `#dce3ec`.
- System sans serif; 17px base, 16–17px form/content/navigation/table text, 14–15px metadata. Preserve readable text sizes on mobile; let controls wrap rather than shrinking their labels.
- Spacing: 4, 8, 12, 16, 24, 32px. Card radius: 12px; controls: 8px.
- Text and labels, as well as color, distinguish status.

## Interaction

- Review overview: finding progress, approved estimated tax amounts and a short next-step explanation. Finding progress is distinct from full filing readiness.
- Findings: search plus attention, waiting, approved and all filters. Clear Review action; source references remain directly accessible.
- Detail panel: native modal dialog, Escape, contained focus, focus return, close button, and a back path through connected records. Separate review, questions/decisions and evidence views. Keep form state while switching views.
- Correction entry and detailed history expand on demand. Technical record JSON expands on demand.
- Client summary: readable jurisdiction amounts; no raw JSON on the landing view.
- Narrow screens: horizontally scrollable navigation, stacked cards, full-width detail panel, scrollable data tables. Never shrink the whole desktop layout.
- Controls have 44px minimum height, visible keyboard focus, explicit labels and reduced-motion support. No font download or new UI dependency required.

## Scope

Preserve authorization, source links, original values, proposal/verification/review logic and all filing controls. Do not make apparent progress or readiness up for presentation purposes. Do not imply a real tax-engine calculation or real filing.
