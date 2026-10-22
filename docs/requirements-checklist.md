# Requirement coverage tracker

A written scaffold is not a completed workflow. Use the demo stories in `plan.md` as the implementation sequence.

| Capability | Main surface | Delivery | Current state |
| --- | --- | --- | --- |
| Exact source tracing, reverse usage, simulated documents | Evidence drawer/library | Foundation + A | API/runtime checked; 2,672 automatic anchors plus manual selection UI; visual review blocked |
| Verification and original-preserving corrections | Claim view | A | Implemented and PostgreSQL-tested: proposals, methods/evidence, original/approved values, approval/rejection and queue status |
| Independent checks, books-to-tax and state allocation | Queue / generated views | Audit + B + breadth | 14 discrepancies and 15 lead dispositions; arithmetic checks pass; full tax-area views remain later work |
| Large sales/asset detail | Generated views | C + breadth | Not implemented |
| Roles, masking, sensitive views | Server API / role selector | Foundation | Unit and PostgreSQL/API role, masking, manual-save and session checks pass |
| Judgment, elections, due diligence, penalties | Claim decisions | C + breadth | Not implemented |
| Version compare, live changes, what-ifs | History / scenarios | D | Version-scoped data foundation only |
| Bulk actions and undo | Queue/detail selection | C | Not implemented |
| Questions, attachments, assignments, deadlines, notifications | Claim view / client view | C + breadth | Not implemented |
| Review notes, sign-offs and reopening | Claim view / readiness | A/B/E | Independent correction review implemented; current-verification checks and stale detection tested. Broader notes/readiness and reopening remain later work |
| Extension, signature, filing/rejection, client copy | Filing | E | Not implemented |
| Freeze, amendment, notice response, carryforward, planning | Filing/history | E | Not implemented |
| Standards, budget/time, status/search, retention | Firm | Breadth | Not implemented |
| Expected CPA records, prior-year comparisons and completeness | Generated views / library | D + breadth | Not implemented |
| Hosted link, one-page concept/model, error report, video, AI disclosure | Submission | Final | Initial demo error list/report finalized; other deliverables pending |
