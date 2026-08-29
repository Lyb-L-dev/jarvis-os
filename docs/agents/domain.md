# Domain Docs

Jarvis OS uses a single-context domain-documentation layout.

## Before exploring

Before changing a domain area:

1. Read `CONTEXT.md` at the repository root when it exists.
2. Read the ADRs under `docs/adr/` that affect the area being changed.
3. Use terminology defined by the domain glossary consistently in issues, code, tests and documentation.

If `CONTEXT.md` does not exist, proceed without warning. The `domain-modeling`, `grill-with-docs` or `improve-codebase-architecture` skills may create it later when domain terms are actually resolved.

## File structure

```text
/
├── CONTEXT.md
├── docs/
│   └── adr/
└── apps/
```

`CONTEXT.md` is the shared glossary and domain model for the repository. `docs/adr/` contains architectural decisions and their rationale.

## Use the glossary vocabulary

When naming a domain concept in an issue title, refactoring proposal, hypothesis, test or implementation, use the term defined in `CONTEXT.md`.

If a required concept is absent, determine whether the proposed term conflicts with existing project language. Record genuine gaps for `domain-modeling`.

## Flag ADR conflicts

If proposed work contradicts an existing ADR, surface the conflict explicitly instead of silently overriding the decision:

> Contradicts ADR-XXXX — worth reconsidering because …
