# ADR 0001: We record architecture decisions here

Date: 2026-10-23
Status: Accepted
Author: Dog254

---

## Context

As the engine grows, we will make many technical decisions — about data models,
matching algorithms, API design, security, infrastructure and more. Without a
record, these decisions are forgotten, repeated by new team members, or
reversed without understanding why they were made in the first place.

## Decision

We will record every significant architecture decision as an ADR (Architecture
Decision Record) in this folder (`docs/adr/`).

An ADR is a short document that captures:
- The context (what situation forced a decision)
- The decision itself
- The reasons for it
- The consequences (what becomes easier, what becomes harder)

ADRs are numbered sequentially and never deleted. If a decision is reversed,
a new ADR is written to record the reversal, and the old ADR is marked
"Superseded by ADR NNNN".

## Format

```
# ADR NNNN: Title

Date: YYYY-MM-DD
Status: Proposed | Accepted | Superseded by ADR NNNN
Author: name

## Context
## Decision
## Reasons
## Consequences
```

## What counts as a significant decision?

- Choosing a technology (database, framework, library, hosting)
- A non-obvious data model choice
- A security policy
- A change to the API contract
- A change to how data enters the engine
- Anything where a new team member would ask "why did you do it this way?"

## Consequences

- New team members can understand the reasoning behind the current design
  without asking.
- Decisions can be revisited with full context.
- The cost is small: a good ADR takes 15 to 30 minutes to write.
