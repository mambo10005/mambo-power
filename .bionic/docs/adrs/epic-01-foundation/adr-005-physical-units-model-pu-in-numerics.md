---
governing-skill: agent-skills:documentation-and-adrs
sdlc-step: 7
intent: build
rigor: audited
scale: wave
canonical_sdlc_version: 13
surface_type: library
language: python
has_ui: false
multi_agent: true
deploy_target: pypi
cleanup_on_finish: true
use_worktree: true
model_plan: see wave-01-substrate.plan.md
---

# ADR-005: Physical units in the model; per-unit only inside `numerics`; validation reports every issue

Status: accepted (wave M1, 2026-08-20; ratified with the M1 spec's Design section, "ok"/"approved").

## Context

Every later wave (power flow, OPF, markets, interop) reads the same `Network`. Two choices
made in M1 cannot be changed later without a schema bump and a rewrite of every consumer:
what units the model stores, and how validation failures are reported.

## Decision

1. **Units.** `Network` stores physical quantities — MW, MVAr, kV, MWh, degrees — with branch
   r/x/b in per-unit on `base_mva`, exactly as MATPOWER and pandapower files do. Per-unit
   conversion happens in exactly one place, `numerics.NetworkArrays.from_network`, which
   is also the only site holding positional indices (`model` exposes none — M1's fold
   removed `Network.bus_index()`). The agreement test is the pandapower `makeYbus` parity
   on the five IEEE fixtures, which fails if the conversion drifts.
2. **Validation.** `Network` construction and `model_validate_json` run every cross-entity
   invariant in one pass and raise `NetworkValidationError` carrying the full list of
   `ValidationIssue(code, path, message)` — codes NO_SLACK, MULTIPLE_SLACK,
   DISCONNECTED_BUS, DUPLICATE_ID, DANGLING_REF, BAD_BASE, BAD_RANGE. The error subclasses
   `Exception`, not `ValueError`, because pydantic wraps a `ValueError` raised inside a
   validator and drops the issue list (plan A5). Range and base bounds live in that
   validator rather than in pydantic `Field` constraints so one pass reports everything
   (A6); the JSON schema therefore carries bounds as description text. Non-finite floats
   are rejected at the model boundary (`allow_inf_nan=False`, M1 fold).
3. **Re-check entry.** Models are mutable and mutation never re-validates;
   `validate_network(net) -> list[ValidationIssue]` is the public re-check (A7).

## Consequences

- Serves epic R1 (JSON-native model), R10 (a service can return every problem in one
  response), and the epic ownership table (§3: one pu-conversion site).
- Files stay human-readable and lossless against MATPOWER / pandapower / PSS/E (M8).
- Callers must `except NetworkValidationError`, not `except ValueError` — documented in M9.
- Machine-readable bounds in the JSON schema (`json_schema_extra`) remain an open
  candidate; adding them is additive and needs only a snapshot regeneration.
- Rejected: pu-in-model (lossy interop, unreadable files); `Field(gt=0)` constraints
  (first-error-only reporting); `ValueError` subclass (issue list lost).
