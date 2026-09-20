# Domain Documentation

When engineering skills explore the codebase, they should follow these rules to read the domain documentation of this repository.

## Read Before Exploration

- `CONTEXT.md` in the root directory
- If `CONTEXT-MAP.md` exists in the root directory, read the relevant `CONTEXT.md` files related to the current topic according to its guidance
- Read ADRs in `docs/adr/` relevant to the current working area
- Multi-context repositories should also check context-level decisions in `src/<context>/docs/adr/`

If the above files do not exist, proceed directly without reporting missing files or proactively suggesting their creation. The `/domain-modeling` skill will create them on demand once terms or decisions are firmly established.

## File Structure

This repository uses a single-context layout:

```text
/
├── CONTEXT.md
├── docs/adr/
│   └── 0001-keep-qoder-behind-the-dsh-llm-boundary.md
└── src/
```

If it changes to a multi-context layout in the future, use:

```text
/
├── CONTEXT-MAP.md
├── docs/adr/                         ← System-level decisions
└── src/
    ├── context-a/
    │   ├── CONTEXT.md
    │   └── docs/adr/                 ← Context-level decisions
    └── context-b/
        ├── CONTEXT.md
        └── docs/adr/
```

## Use Terms from the Glossary

When output requires naming domain concepts—such as issue titles, refactoring proposals, hypotheses, or test names—use the terminology defined in `CONTEXT.md`. Do not substitute with synonyms that the glossary explicitly advises against.

If the glossary does not yet define a needed concept, verify whether the term is truly not part of the project language. If an actual vocabulary gap exists, record it for handling by `/domain-modeling`.

## Flag ADR Conflicts

If output conflicts with an existing ADR, explicitly state the conflict rather than silently overriding it:

> Conflicts with ADR-0007 (Event Sourcing Orders), but worth reopening because...
