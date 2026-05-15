# Argument Review Protocol

This repo uses two short argument files to keep design and implementation
changes honest:

- `codexArg`
- `claudeArg`

The goal is to create a lightweight third-party review loop without adding a
workflow framework, ledger, or phase system.

## Why These Files Exist

The previous repo drifted because broad helpers, hidden defaults, registries,
bootstrap columns, and local invariants accumulated faster than they were
reviewed.

These files force each change to be explained in plain language before it is
accepted as the next step.

They are intentionally overwritten each time. They are not a permanent history
or audit log.

## Codex Responsibility

After Codex makes a repo change, and before Codex proposes a meaningful next
change, Codex must overwrite `codexArg`.

`codexArg` must state:

- what changed or is being proposed
- why it was done
- which files were touched or would be touched
- what assumptions were made
- what risks or open questions remain

Codex should keep the entry short. The point is to expose the reasoning, not to
write a long report.

## Claude Responsibility

Claude should read:

- the latest repo changes or proposal
- `codexArg`
- the relevant touched files

Claude should then overwrite `claudeArg` with its review.

`claudeArg` should state:

- whether the change matches the repo rules
- whether it introduces hidden abstraction, bootstrap behavior, or silent drift
- whether the reasoning in `codexArg` is sound
- what should change before proceeding, if anything

Claude should keep the review short and specific.

## Important Boundaries

These files do not approve code automatically.

They do not replace tests.

They do not create a workflow engine.

They do not permit broad abstractions, universal bootstrap layers, strategy
registries, or hidden defaults.

They are only a lightweight review surface for the current change.

## Expected Usage

For documentation-only changes:

```text
Codex writes or updates the doc.
Codex overwrites codexArg with the reason and touched files.
Claude reviews the doc and codexArg.
Claude overwrites claudeArg with agreement, objections, or requested changes.
```

For code changes:

```text
Codex makes the smallest scoped code change.
Codex overwrites codexArg with the reason, touched files, assumptions, and risk.
Claude reviews the code and codexArg.
Claude overwrites claudeArg with agreement, objections, or requested changes.
```

For proposals before coding:

```text
Codex overwrites codexArg with the proposed files and reasoning.
Claude reviews the proposal before implementation starts.
```
