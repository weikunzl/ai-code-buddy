# ADR-0008: Treat Multi-Choice As A Separate Milestone

## Status

Accepted

## Context

`single_choice` is now verified end to end over the current bridge and on
hardware. The remaining prompt-product gap is multi-choice.

Multi-choice is not just another option payload. It changes the device
interaction contract:

- firmware must maintain both a cursor and a selection set,
- prompt-mode `A hold` can no longer always open the menu,
- the bridge must accept `choices[]` arrays and validate them,
- simulator and protocol docs need a distinct answer shape.

## Decision

Treat `multi_choice` as its own post-single-choice milestone.

This slice includes:

- bridge support for `choices[]`,
- simulator support for a bounded `multi` profile,
- firmware-local per-option selected state,
- prompt-mode button handling for toggle/next/submit,
- protocol documentation and hardware verification.

This slice does not include:

- free-text prompt entry,
- keyboard/text composition,
- unlimited option counts,
- persisted partial prompt state,
- host hook integration for real multi-choice producers.

## Rationale

This keeps the interaction contract explicit and avoids conflating a working
single-choice path with a more complex multi-select flow.

The device constraints are still the same:

- two buttons,
- small portrait screen,
- bounded prompt count and bounded options,
- host bridge remains authoritative for pending state.

## Consequences

- Multi-choice needs a device grammar:
  - `A click`: toggle current option
  - `B click`: move cursor
  - `A hold`: submit selected options
- Prompt-mode long-press handling must become kind-aware so menu-open does
  not steal multi-choice submit.
- The bridge must validate `choices[]` for membership and uniqueness before
  accepting the answer.
